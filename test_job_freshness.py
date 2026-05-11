import unittest
from datetime import datetime, timedelta

from job_freshness import assess_job_freshness


class JobFreshnessTests(unittest.TestCase):
    def test_apply_today_is_not_treated_as_posted_today(self):
        result = assess_job_freshness(
            title="Analytical Development Scientist",
            description="Apply today to join our analytical chemistry team.",
            url="https://example.com/careers/123",
            source="direct",
        )
        self.assertTrue(result["keep"])
        self.assertFalse(result["verified"])
        self.assertIsNone(result["date_posted"])

    def test_posted_today_is_verified(self):
        result = assess_job_freshness(
            title="Analytical Development Scientist",
            description="Posted today. Apply to join our analytical chemistry team.",
            url="https://example.com/careers/123",
            source="direct",
        )
        self.assertTrue(result["keep"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["days_old"], 0)

    def test_closed_loop_materials_does_not_mark_inactive(self):
        result = assess_job_freshness(
            title="Battery Materials Scientist",
            description="Experience with closed-loop recycling and materials characterization preferred.",
            url="https://example.com/careers/456",
            source="direct",
        )
        self.assertTrue(result["keep"])
        self.assertTrue(result["active"])

    def test_explicit_stale_date_is_rejected(self):
        stale_date = (datetime.now() - timedelta(days=181)).strftime("%Y-%m-%d")
        result = assess_job_freshness(
            title="Analytical Development Scientist",
            description="Active posting",
            url="https://example.com/careers/789",
            source="direct",
            explicit_date_posted=stale_date,
        )
        self.assertFalse(result["keep"])
        self.assertFalse(result["active"])


if __name__ == "__main__":
    unittest.main()
