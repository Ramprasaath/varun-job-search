#!/usr/bin/env node
/**
 * validate_varun_tracker.mjs — integrity checks for Varun's JSON tracker.
 *
 * This complements the upstream career-ops verifier, which checks
 * data/applications.md. Varun's hosted Streamlit app uses data/jobs.json.
 */

import { existsSync, readFileSync } from 'fs';
import { basename, dirname, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(ROOT, 'data');
const JOBS_PATH = join(DATA_DIR, 'jobs.json');
const ARCHIVE_PATH = join(DATA_DIR, 'archived_jobs.json');
const CONTACTS_PATH = join(DATA_DIR, 'contacts.json');
const RESUME_DIR = join(DATA_DIR, 'resume');

const STATUSES = new Set(['discovered', 'evaluated', 'interested', 'applying', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn']);
const CONTACT_STATUSES = new Set(['not_contacted', 'search_placeholder', 'request_sent', 'responded', 'call_scheduled', 'met']);
const CONTACT_TYPES = new Set(['hiring_manager', 'team_lead', 'recruiter', 'peer', 'ceo', 'search_placeholder']);

let errors = 0;
let warnings = 0;

function error(message) {
  console.log(`ERROR ${message}`);
  errors += 1;
}

function warn(message) {
  console.log(`WARN  ${message}`);
  warnings += 1;
}

function ok(message) {
  console.log(`OK    ${message}`);
}

function readJson(path, fallback = []) {
  if (!existsSync(path)) {
    error(`Missing required file: ${rel(path)}`);
    return fallback;
  }
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (err) {
    error(`Invalid JSON in ${rel(path)}: ${err.message}`);
    return fallback;
  }
}

function rel(path) {
  return path.replace(`${ROOT}/`, '');
}

function isoDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function normalizeText(value) {
  return String(value || '').toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, ' ');
}

function resumeVersion(value) {
  if (!value) return '';
  const name = basename(String(value).trim());
  return name.endsWith('.json') ? name.slice(0, -5) : name;
}

function checkUniqueIds(items, label) {
  const seen = new Map();
  for (const item of items) {
    if (item.id === undefined || item.id === null) {
      error(`${label} item missing id: ${JSON.stringify(item).slice(0, 120)}`);
      continue;
    }
    if (seen.has(item.id)) {
      error(`${label} duplicate id ${item.id}`);
    }
    seen.set(item.id, item);
  }
  ok(`${label} ids checked`);
}

const jobs = readJson(JOBS_PATH);
const archived = readJson(ARCHIVE_PATH);
const contacts = readJson(CONTACTS_PATH);

if (!Array.isArray(jobs)) error('data/jobs.json must contain an array');
if (!Array.isArray(archived)) error('data/archived_jobs.json must contain an array');
if (!Array.isArray(contacts)) error('data/contacts.json must contain an array');

checkUniqueIds(jobs, 'active jobs');
checkUniqueIds(archived, 'archived jobs');
checkUniqueIds(contacts, 'contacts');

const activeIds = new Set(jobs.map(job => job.id));
const archivedIds = new Set(archived.map(job => job.id));
for (const job of archived) {
  if (activeIds.has(job.id)) error(`Job #${job.id} exists in both active and archived trackers`);
}

const exactJobKeys = new Map();
for (const job of jobs) {
  for (const field of ['id', 'company', 'title', 'url', 'date_found', 'status']) {
    if (job[field] === undefined || job[field] === null || job[field] === '') {
      error(`Job #${job.id ?? '?'} missing required field "${field}"`);
    }
  }

  if (!STATUSES.has(job.status)) error(`Job #${job.id} has non-canonical status "${job.status}"`);
  if (job.score !== null && job.score !== undefined && (typeof job.score !== 'number' || job.score < 0 || job.score > 5)) {
    error(`Job #${job.id} has invalid score ${JSON.stringify(job.score)}`);
  }
  for (const field of ['date_found', 'date_posted', 'applied_date', 'follow_up_date']) {
    if (job[field] && !isoDate(job[field])) error(`Job #${job.id} has invalid ${field}: ${job[field]}`);
  }

  const key = `${normalizeText(job.company)}::${normalizeText(job.title)}`;
  if (exactJobKeys.has(key)) {
    error(`Possible duplicate active job: #${exactJobKeys.get(key).id} and #${job.id} (${job.company} — ${job.title})`);
  } else {
    exactJobKeys.set(key, job);
  }

  const version = resumeVersion(job.tailored_resume);
  if (job.tailored_resume && !version) error(`Job #${job.id} has malformed tailored_resume value`);
  if (version && !existsSync(join(RESUME_DIR, `${version}.json`))) {
    error(`Job #${job.id} tailored resume missing: data/resume/${version}.json`);
  }
  if (job.pdf_path && !existsSync(join(ROOT, job.pdf_path))) {
    error(`Job #${job.id} PDF missing: ${job.pdf_path}`);
  }
  if (job.report_path && !existsSync(join(ROOT, job.report_path))) {
    error(`Job #${job.id} report missing: ${job.report_path}`);
  }
  if (typeof job.score === 'number' && job.score >= 4.0) {
    if (!version) warn(`Job #${job.id} is >=4.0 but has no tailored_resume`);
    if (!job.pdf_path) warn(`Job #${job.id} is >=4.0 but has no pdf_path`);
  }
}
ok('active job records checked');

const allJobIds = new Set([...activeIds, ...archivedIds]);
for (const contact of contacts) {
  if (!allJobIds.has(contact.job_id)) error(`Contact #${contact.id} points to missing job_id ${contact.job_id}`);
  if (contact.status && !CONTACT_STATUSES.has(contact.status)) error(`Contact #${contact.id} has non-canonical status "${contact.status}"`);
  if (contact.contact_type && !CONTACT_TYPES.has(contact.contact_type)) error(`Contact #${contact.id} has unknown contact_type "${contact.contact_type}"`);
  if (contact.date_contacted && !isoDate(contact.date_contacted)) error(`Contact #${contact.id} has invalid date_contacted: ${contact.date_contacted}`);
}
ok('contact records checked');

const resumeFiles = readJson(join(RESUME_DIR, 'base_resume.json'), {});
if (!resumeFiles || typeof resumeFiles !== 'object' || Array.isArray(resumeFiles)) {
  error('data/resume/base_resume.json must contain an object');
} else {
  ok('base resume JSON checked');
}

console.log(`\nVarun tracker validation: ${errors} error(s), ${warnings} warning(s)`);
if (errors > 0) process.exit(1);
