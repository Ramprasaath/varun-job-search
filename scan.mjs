#!/usr/bin/env node

/**
 * scan.mjs — Hybrid portal scanner
 *
 * Sources:
 * - Direct ATS APIs when possible (Greenhouse, Ashby, Lever, Workday)
 * - Career page discovery for hidden ATS backends
 * - Brave web search queries from portals.yml when BRAVE_API_KEY is available
 *
 * Usage:
 *   node scan.mjs
 *   node scan.mjs --dry-run
 *   node scan.mjs --company Pfizer
 */

import { readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync } from 'fs';
import yaml from 'js-yaml';
const parseYaml = yaml.load;

const PORTALS_PATH = 'portals.yml';
const SCAN_HISTORY_PATH = 'data/scan-history.tsv';
const PIPELINE_PATH = 'data/pipeline.md';
const APPLICATIONS_PATH = 'data/applications.md';

mkdirSync('data', { recursive: true });

const CONCURRENCY = 8;
const FETCH_TIMEOUT_MS = 10_000;
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';
const BRAVE_API_KEY = process.env.BRAVE_API_KEY;
const BRAVE_RESULTS_PER_QUERY = Number(process.env.BRAVE_RESULTS_PER_QUERY || 5);
const BRAVE_SEARCH_DELAY_MS = Number(process.env.BRAVE_SEARCH_DELAY_MS || 1100);
const SCAN_MAX_QUERIES = Number(process.env.SCAN_MAX_QUERIES || 0);

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function normalizeUrl(rawUrl) {
  if (!rawUrl) return '';
  try {
    const url = new URL(rawUrl);
    url.hash = '';
    const noisyParams = [
      'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
      'gh_src', 'gh_jid', 'gh_jid', 'gh_src', 'source', 'src', 'ref', 'referrer',
      'fbclid', 'gclid', 'mc_cid', 'mc_eid'
    ];
    for (const key of noisyParams) url.searchParams.delete(key);
    return url.toString();
  } catch {
    return rawUrl.trim();
  }
}

function uniqueBy(items, keyFn) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const key = keyFn(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function buildTitleFilter(titleFilter) {
  const positive = (titleFilter?.positive || []).map(k => k.toLowerCase());
  const negative = (titleFilter?.negative || []).map(k => k.toLowerCase());

  return (title) => {
    const lower = (title || '').toLowerCase();
    const hasPositive = positive.length === 0 || positive.some(k => lower.includes(k));
    const hasNegative = negative.some(k => lower.includes(k));
    return hasPositive && !hasNegative;
  };
}

function detectApi(company) {
  if (company.api) {
    if (company.api.includes('greenhouse')) return { type: 'greenhouse', url: company.api };
    if (company.api.includes('ashbyhq')) return { type: 'ashby', url: company.api };
    if (company.api.includes('lever.co')) return { type: 'lever', url: company.api };
    if (company.api.includes('/wday/cxs/')) {
      return {
        type: 'workday',
        url: company.api,
        method: 'POST',
        siteUrl: company.careers_url,
        body: { appliedFacets: {}, limit: 20, offset: 0, searchText: '' },
      };
    }
  }

  const raw = company.careers_url || '';
  if (!raw) return null;

  try {
    const url = new URL(raw);

    const ashbyMatch = raw.match(/jobs\.ashbyhq\.com\/([^/?#]+)/i);
    if (ashbyMatch) {
      return {
        type: 'ashby',
        url: `https://api.ashbyhq.com/posting-api/job-board/${ashbyMatch[1]}?includeCompensation=true`,
      };
    }

    const leverMatch = raw.match(/jobs\.lever\.co\/([^/?#]+)/i);
    if (leverMatch) {
      return {
        type: 'lever',
        url: `https://api.lever.co/v0/postings/${leverMatch[1]}`,
      };
    }

    const ghMatch = raw.match(/job-boards(?:\.eu)?\.greenhouse\.io\/([^/?#]+)/i);
    if (ghMatch) {
      return {
        type: 'greenhouse',
        url: `https://boards-api.greenhouse.io/v1/boards/${ghMatch[1]}/jobs`,
      };
    }

    if (url.hostname.includes('myworkdayjobs.com')) {
      const parts = url.pathname.split('/').filter(Boolean);
      const site = parts[parts.length - 1];
      const tenant = url.hostname.split('.')[0];
      if (site && tenant) {
        return {
          type: 'workday',
          url: `${url.origin}/wday/cxs/${tenant}/${site}/jobs`,
          method: 'POST',
          siteUrl: raw,
          body: { appliedFacets: {}, limit: 20, offset: 0, searchText: '' },
        };
      }
    }
  } catch {
    return null;
  }

  return null;
}

function buildGreenhouseEndpoint(slug) {
  return { type: 'greenhouse', url: `https://boards-api.greenhouse.io/v1/boards/${slug}/jobs` };
}

function buildAshbyEndpoint(slug) {
  return { type: 'ashby', url: `https://api.ashbyhq.com/posting-api/job-board/${slug}?includeCompensation=true` };
}

function buildLeverEndpoint(slug) {
  return { type: 'lever', url: `https://api.lever.co/v0/postings/${slug}` };
}

function buildWorkdayEndpoint(origin, tenant, site, siteUrl = origin) {
  return {
    type: 'workday',
    url: `${origin}/wday/cxs/${tenant}/${site}/jobs`,
    method: 'POST',
    siteUrl,
    body: { appliedFacets: {}, limit: 20, offset: 0, searchText: '' },
  };
}

async function fetchJson(endpoint) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const method = endpoint.method || 'GET';
    const headers = {
      'user-agent': USER_AGENT,
      accept: 'application/json',
      ...(endpoint.headers || {}),
    };
    const options = { method, signal: controller.signal, headers };
    if (endpoint.body && method !== 'GET') {
      headers['content-type'] = 'application/json';
      options.body = JSON.stringify(endpoint.body);
    }
    const res = await fetch(endpoint.url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

async function fetchText(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        'user-agent': USER_AGENT,
        accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      },
      redirect: 'follow',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.text();
  } finally {
    clearTimeout(timer);
  }
}

function parseGreenhouse(json, companyName) {
  return (json.jobs || []).map(j => ({
    title: j.title || '',
    url: normalizeUrl(j.absolute_url || ''),
    company: companyName,
    location: j.location?.name || '',
  }));
}

function parseAshby(json, companyName) {
  return (json.jobs || []).map(j => ({
    title: j.title || '',
    url: normalizeUrl(j.jobUrl || ''),
    company: companyName,
    location: typeof j.location === 'string' ? j.location : (j.location?.locationName || ''),
  }));
}

function parseLever(json, companyName) {
  if (!Array.isArray(json)) return [];
  return json.map(j => ({
    title: j.text || '',
    url: normalizeUrl(j.hostedUrl || ''),
    company: companyName,
    location: j.categories?.location || '',
  }));
}

function parseWorkday(json, companyName, endpoint) {
  const origin = endpoint.siteUrl ? new URL(endpoint.siteUrl).origin : new URL(endpoint.url).origin;
  return (json.jobPostings || []).map(j => ({
    title: j.title || '',
    url: normalizeUrl(j.externalPath ? new URL(j.externalPath, origin).toString() : ''),
    company: companyName,
    location: j.locationsText || j.location || '',
  }));
}

async function fetchWorkdayJobs(endpoint, companyName) {
  const pageSize = endpoint.body?.limit || 100;
  let offset = 0;
  let total = Infinity;
  const jobs = [];

  while (offset < total && offset < 500) {
    const json = await fetchJson({
      ...endpoint,
      body: { ...(endpoint.body || {}), offset },
    });
    jobs.push(...parseWorkday(json, companyName, endpoint));
    total = Number(json.total || jobs.length);
    if (!(json.jobPostings || []).length) break;
    offset += pageSize;
  }

  return jobs;
}

const PARSERS = {
  greenhouse: parseGreenhouse,
  ashby: parseAshby,
  lever: parseLever,
};

function loadSeenUrls() {
  const seen = new Set();

  if (existsSync(SCAN_HISTORY_PATH)) {
    const lines = readFileSync(SCAN_HISTORY_PATH, 'utf-8').split('\n');
    for (const line of lines.slice(1)) {
      const url = line.split('\t')[0];
      if (url) seen.add(normalizeUrl(url));
    }
  }

  if (existsSync(PIPELINE_PATH)) {
    const text = readFileSync(PIPELINE_PATH, 'utf-8');
    for (const match of text.matchAll(/- \[[ x]\] (https?:\/\/\S+)/g)) {
      seen.add(normalizeUrl(match[1]));
    }
  }

  if (existsSync(APPLICATIONS_PATH)) {
    const text = readFileSync(APPLICATIONS_PATH, 'utf-8');
    for (const match of text.matchAll(/https?:\/\/[^\s|)]+/g)) {
      seen.add(normalizeUrl(match[0]));
    }
  }

  return seen;
}

function loadSeenCompanyRoles() {
  const seen = new Set();
  if (!existsSync(APPLICATIONS_PATH)) return seen;

  const text = readFileSync(APPLICATIONS_PATH, 'utf-8');
  for (const match of text.matchAll(/\|[^|]+\|[^|]+\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|/g)) {
    const company = match[1].trim().toLowerCase();
    const role = match[2].trim().toLowerCase();
    if (company && role && company !== 'company') {
      seen.add(`${company}::${role}`);
    }
  }
  return seen;
}

function ensurePipelineFile() {
  if (!existsSync(PIPELINE_PATH)) {
    writeFileSync(PIPELINE_PATH, '# Job Pipeline\n\n## Pendientes\n\n## Procesadas\n', 'utf-8');
  }
}

function appendToPipeline(offers) {
  if (offers.length === 0) return;

  ensurePipelineFile();
  let text = readFileSync(PIPELINE_PATH, 'utf-8');
  const marker = '## Pendientes';
  const idx = text.indexOf(marker);

  if (idx === -1) {
    const procIdx = text.indexOf('## Procesadas');
    const insertAt = procIdx === -1 ? text.length : procIdx;
    const block = `\n${marker}\n\n` + offers.map(o => `- [ ] ${o.url} | ${o.company} | ${o.title}`).join('\n') + '\n\n';
    text = text.slice(0, insertAt) + block + text.slice(insertAt);
  } else {
    const afterMarker = idx + marker.length;
    const nextSection = text.indexOf('\n## ', afterMarker);
    const insertAt = nextSection === -1 ? text.length : nextSection;
    const block = '\n' + offers.map(o => `- [ ] ${o.url} | ${o.company} | ${o.title}`).join('\n') + '\n';
    text = text.slice(0, insertAt) + block + text.slice(insertAt);
  }

  writeFileSync(PIPELINE_PATH, text, 'utf-8');
}

function appendToScanHistory(offers, date) {
  if (!existsSync(SCAN_HISTORY_PATH)) {
    writeFileSync(SCAN_HISTORY_PATH, 'url\tfirst_seen\tportal\ttitle\tcompany\tstatus\n', 'utf-8');
  }

  const lines = offers.map(o =>
    `${normalizeUrl(o.url)}\t${date}\t${o.source}\t${o.title}\t${o.company}\tadded`
  ).join('\n') + '\n';

  appendFileSync(SCAN_HISTORY_PATH, lines, 'utf-8');
}

async function parallelFetch(tasks, limit) {
  const results = [];
  let i = 0;

  async function next() {
    while (i < tasks.length) {
      const task = tasks[i++];
      results.push(await task());
    }
  }

  const workers = Array.from({ length: Math.min(limit, tasks.length) }, () => next());
  await Promise.all(workers);
  return results;
}

function discoverEndpointsFromHtml(html, careersUrl) {
  const endpoints = [];
  const origin = (() => {
    try { return new URL(careersUrl).origin; } catch { return ''; }
  })();

  const ghEmbed = html.match(/boards\.greenhouse\.io\/embed\/job_board\/js\?for=([a-z0-9-]+)/i);
  if (ghEmbed) endpoints.push(buildGreenhouseEndpoint(ghEmbed[1]));

  const ghBoard = html.match(/(?:job-boards(?:\.eu)?|boards)\.greenhouse\.io\/([a-z0-9-]+)(?:\/jobs)?/i);
  if (ghBoard) endpoints.push(buildGreenhouseEndpoint(ghBoard[1]));

  const ashby = html.match(/jobs\.ashbyhq\.com\/([a-z0-9-]+)/i);
  if (ashby) endpoints.push(buildAshbyEndpoint(ashby[1]));

  const lever = html.match(/jobs\.lever\.co\/([a-z0-9-]+)/i);
  if (lever) endpoints.push(buildLeverEndpoint(lever[1]));

  const workday = html.match(/\/wday\/cxs\/([^/"'\s<>]+)\/([^/"'\s<>]+)\/jobs/i);
  if (workday && origin) endpoints.push(buildWorkdayEndpoint(origin, workday[1], workday[2], careersUrl));

  return uniqueBy(endpoints, e => `${e.type}:${e.url}`);
}

async function discoverApiFromCareerPage(company) {
  if (!company.careers_url) return [];
  try {
    const html = await fetchText(company.careers_url);
    return discoverEndpointsFromHtml(html, company.careers_url);
  } catch {
    return [];
  }
}

async function fetchCompanyJobs(company) {
  const endpoints = uniqueBy([
    detectApi(company),
    ...(await discoverApiFromCareerPage(company)),
  ].filter(Boolean), e => `${e.type}:${e.url}`);

  if (!endpoints.length) {
    throw new Error('no supported ATS endpoint detected');
  }

  const errors = [];
  for (const endpoint of endpoints) {
    try {
      if (endpoint.type === 'workday') {
        return { jobs: await fetchWorkdayJobs(endpoint, company.name), endpointType: endpoint.type };
      }
      const json = await fetchJson(endpoint);
      const parser = PARSERS[endpoint.type];
      if (!parser) throw new Error(`no parser for ${endpoint.type}`);
      return { jobs: parser(json, company.name, endpoint), endpointType: endpoint.type };
    } catch (err) {
      errors.push(`${endpoint.type}: ${err.message}`);
    }
  }

  throw new Error(errors.join('; '));
}

async function braveSearch(query, count = BRAVE_RESULTS_PER_QUERY) {
  if (!BRAVE_API_KEY) return [];
  const url = new URL('https://api.search.brave.com/res/v1/web/search');
  url.searchParams.set('q', query);
  url.searchParams.set('count', String(count));
  url.searchParams.set('country', 'us');
  url.searchParams.set('search_lang', 'en');
  url.searchParams.set('text_decorations', 'false');
  url.searchParams.set('freshness', 'month');

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        accept: 'application/json',
        'user-agent': USER_AGENT,
        'x-subscription-token': BRAVE_API_KEY,
      },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    return json.web?.results || [];
  } finally {
    clearTimeout(timer);
  }
}

function looksLikeJobUrl(url) {
  const lower = (url || '').toLowerCase();
  return /(\/jobs?\/|careers?|job-boards|greenhouse|lever|ashbyhq|myworkdayjobs|workdayjobs|opening|position|requisition|opportunit|smartrecruiters|workable)/.test(lower);
}

function extractLocation(text) {
  if (!text) return '';
  const patterns = [
    /((?:San Francisco|South San Francisco|Sunnyvale|Santa Clara|San Jose|Milpitas|Fremont|Alameda|Cambridge|Boston|Watertown|San Diego|Carlsbad|Research Triangle|Seattle|Austin|Phoenix|Portland|Indianapolis|New York|Newark|Princeton|Waltham|Gaithersburg|Tarrytown|Corning)(?:,\s*(?:CA|MA|NY|NJ|NC|WA|TX|AZ|OR|IN|MD))?)/i,
    /([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*(?:CA|MA|NY|NJ|NC|WA|TX|AZ|OR|IN|MD|PA|IL|MN|CO|CT))/,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1];
  }
  return '';
}

function inferCompanyFromResult(result, fallbackCompany = '') {
  const title = result.title || '';
  if (fallbackCompany) return fallbackCompany;
  if (/\sat\s/i.test(title)) {
    return title.split(/\sat\s/i).pop().split('|')[0].trim();
  }
  if (/@\s*[A-Z]/.test(title)) {
    return title.split('@').pop().split('|')[0].trim();
  }
  return '';
}

function parseSearchResult(result, fallbackCompany = '') {
  const url = normalizeUrl(result.url || result.profile?.url || '');
  let title = (result.title || '').replace(/\s+/g, ' ').trim();
  const description = (result.description || '').replace(/\s+/g, ' ').trim();

  if (!url || !title || !looksLikeJobUrl(url)) return null;

  title = title
    .replace(/^Job Application for\s+/i, '')
    .replace(/\s*-\s*Myworkdayjobs\.com$/i, '')
    .split('|')[0]
    .trim();

  return {
    title,
    url,
    company: inferCompanyFromResult({ ...result, title }, fallbackCompany),
    location: extractLocation(description),
    description,
  };
}

function buildSearchTargets(config, companies, filterCompany) {
  const queryTargets = [];

  for (const q of config.search_queries || []) {
    if (q.enabled === false) continue;
    if (filterCompany && !(q.name || '').toLowerCase().includes(filterCompany)) continue;
    queryTargets.push({
      label: q.name || q.query,
      query: q.query,
      count: q.count || BRAVE_RESULTS_PER_QUERY,
      companyName: '',
    });
  }

  for (const company of companies) {
    if (company.enabled === false) continue;
    if (filterCompany && !company.name.toLowerCase().includes(filterCompany)) continue;

    if (company.scan_query) {
      queryTargets.push({
        label: `Company watcher - ${company.name}`,
        query: company.scan_query,
        count: company.count || BRAVE_RESULTS_PER_QUERY,
        companyName: company.name,
      });
      continue;
    }

    if (company.careers_url) {
      try {
        const host = new URL(company.careers_url).hostname.replace(/^www\./, '');
        queryTargets.push({
          label: `Company watcher - ${company.name}`,
          query: `site:${host} ("Materials Scientist" OR "Analytical Scientist" OR "Applications Scientist" OR "Process Engineer" OR "Scientist")`,
          count: company.count || BRAVE_RESULTS_PER_QUERY,
          companyName: company.name,
        });
      } catch {
        // noop
      }
    }
  }

  const deduped = uniqueBy(queryTargets, q => q.query.trim().toLowerCase());
  return SCAN_MAX_QUERIES > 0 ? deduped.slice(0, SCAN_MAX_QUERIES) : deduped;
}

function maybeAddOffer(job, source, titleFilter, seenUrls, seenCompanyRoles, stats, output) {
  if (!job || !job.title || !job.url) return;

  const canonicalUrl = normalizeUrl(job.url);
  if (!titleFilter(job.title)) {
    stats.filtered++;
    return;
  }
  if (seenUrls.has(canonicalUrl)) {
    stats.duplicates++;
    return;
  }

  const company = job.company || 'Unknown';
  const key = `${company.toLowerCase()}::${job.title.toLowerCase()}`;
  if (seenCompanyRoles.has(key)) {
    stats.duplicates++;
    return;
  }

  seenUrls.add(canonicalUrl);
  seenCompanyRoles.add(key);
  output.push({
    ...job,
    url: canonicalUrl,
    company,
    source,
  });
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const companyFlag = args.indexOf('--company');
  const filterCompany = companyFlag !== -1 ? args[companyFlag + 1]?.toLowerCase() : null;

  if (!existsSync(PORTALS_PATH)) {
    console.error('Error: portals.yml not found. Run onboarding first.');
    process.exit(1);
  }

  const config = parseYaml(readFileSync(PORTALS_PATH, 'utf-8'));
  const companies = (config.tracked_companies || [])
    .filter(c => c.enabled !== false)
    .filter(c => !filterCompany || c.name.toLowerCase().includes(filterCompany));
  const titleFilter = buildTitleFilter(config.title_filter);

  const apiCandidates = companies.filter(c => c.api || /(?:greenhouse|ashbyhq|lever\.co|myworkdayjobs\.com)/i.test(c.careers_url || ''));
  const queryTargets = buildSearchTargets(config, companies, filterCompany);

  console.log(`Scanning ${apiCandidates.length} ATS-backed companies`);
  console.log(`Web query targets: ${queryTargets.length}${BRAVE_API_KEY ? '' : ' (BRAVE_API_KEY missing, web search disabled)'}`);
  if (dryRun) console.log('(dry run — no files will be written)\n');

  const seenUrls = loadSeenUrls();
  const seenCompanyRoles = loadSeenCompanyRoles();
  const date = new Date().toISOString().slice(0, 10);
  const newOffers = [];

  const stats = {
    totalFound: 0,
    filtered: 0,
    duplicates: 0,
    apiCompaniesScanned: 0,
    apiErrors: [],
    apiHits: 0,
    webQueriesRun: 0,
    webErrors: [],
    webHits: 0,
  };

  const apiTasks = apiCandidates.map(company => async () => {
    try {
      const { jobs, endpointType } = await fetchCompanyJobs(company);
      stats.apiCompaniesScanned++;
      stats.totalFound += jobs.length;
      stats.apiHits += jobs.length;
      for (const job of jobs) {
        maybeAddOffer(job, `${endpointType}-api`, titleFilter, seenUrls, seenCompanyRoles, stats, newOffers);
      }
    } catch (err) {
      stats.apiErrors.push({ company: company.name, error: err.message });
    }
  });

  await parallelFetch(apiTasks, CONCURRENCY);

  if (BRAVE_API_KEY) {
    for (const target of queryTargets) {
      try {
        const results = await braveSearch(target.query, target.count || BRAVE_RESULTS_PER_QUERY);
        stats.webQueriesRun++;
        stats.totalFound += results.length;
        stats.webHits += results.length;
        for (const result of results) {
          maybeAddOffer(parseSearchResult(result, target.companyName), 'brave-web', titleFilter, seenUrls, seenCompanyRoles, stats, newOffers);
        }
      } catch (err) {
        stats.webErrors.push({ query: target.label, error: err.message });
      }
      await delay(BRAVE_SEARCH_DELAY_MS);
    }
  }

  if (!dryRun && newOffers.length > 0) {
    appendToPipeline(newOffers);
    appendToScanHistory(newOffers, date);
  }

  console.log(`\n${'━'.repeat(45)}`);
  console.log(`Portal Scan — ${date}`);
  console.log(`${'━'.repeat(45)}`);
  console.log(`ATS companies attempted: ${apiCandidates.length}`);
  console.log(`ATS jobs fetched:        ${stats.apiHits}`);
  console.log(`Web queries run:         ${stats.webQueriesRun}`);
  console.log(`Web results fetched:     ${stats.webHits}`);
  console.log(`Total raw results:       ${stats.totalFound}`);
  console.log(`Filtered by title:       ${stats.filtered} removed`);
  console.log(`Duplicates:              ${stats.duplicates} skipped`);
  console.log(`New offers added:        ${newOffers.length}`);

  if (stats.apiErrors.length > 0) {
    console.log(`\nATS Errors (${stats.apiErrors.length}):`);
    for (const e of stats.apiErrors) console.log(`  ✗ ${e.company}: ${e.error}`);
  }

  if (stats.webErrors.length > 0) {
    console.log(`\nWeb Search Errors (${stats.webErrors.length}):`);
    for (const e of stats.webErrors) console.log(`  ✗ ${e.query}: ${e.error}`);
  }

  if (newOffers.length > 0) {
    console.log('\nNew offers:');
    for (const offer of newOffers) {
      console.log(`  + ${offer.company} | ${offer.title} | ${offer.location || 'N/A'} | ${offer.source}`);
    }
    if (dryRun) {
      console.log('\n(dry run — run without --dry-run to save results)');
    } else {
      console.log(`\nResults saved to ${PIPELINE_PATH} and ${SCAN_HISTORY_PATH}`);
    }
  }

  console.log(`\n→ Run /career-ops pipeline to evaluate new offers.`);
}

main().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
