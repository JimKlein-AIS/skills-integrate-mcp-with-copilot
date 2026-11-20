import json
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/find-exercise-issue.yml"


class FindExerciseIssueTests(unittest.TestCase):
    def run_finder(self, pages, title="Exercise"):
        script = textwrap.dedent(WORKFLOW.read_text().split("          script: |\n", 1)[1])
        harness = """
          const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
          const calls = [];
          const outputs = {};
          const github = {rest: {issues: {listForRepo: async params => {
            calls.push(params);
            return {data: input.pages[params.page - 1] || []};
          }}}};
          const core = {info: () => {}, setOutput: (key, value) => outputs[key] = value};
          const context = {repo: {owner: 'owner', repo: 'repo'}};
          process.env.ISSUE_TITLE_PREFIX = input.title;
          const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
          new AsyncFunction('github', 'core', 'context', input.script)(github, core, context)
            .then(() => console.log(JSON.stringify({calls, outputs})))
            .catch(error => console.log(JSON.stringify({calls, outputs, error: error.message})));
        """
        result = subprocess.run(
            ["node", "-e", harness],
            input=json.dumps({"script": script, "pages": pages, "title": title}),
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_finds_older_issue_after_full_page_including_pull_requests(self):
        page = [{"title": "Other", "number": n} for n in range(100)]
        page[0] = {"title": "Exercise pull request", "pull_request": {}, "number": 101}
        issue = {"title": "Exercise: Integrate MCP", "number": 1, "html_url": "https://example.com/1"}
        result = self.run_finder([page, [issue]])
        self.assertEqual(result["outputs"], {"ISSUE_URL": issue["html_url"], "ISSUE_NUMBER": 1})
        self.assertEqual([call["page"] for call in result["calls"]], [1, 2])
        self.assertTrue(all(call["state"] == "all" and call["direction"] == "desc"
                            and call["per_page"] == 100 for call in result["calls"]))

    def test_returns_newest_matching_issue_and_honors_title_input(self):
        first = {"title": "Custom exercise", "number": 3, "html_url": "https://example.com/3"}
        second = {"title": "Custom exercise", "number": 2, "html_url": "https://example.com/2"}
        result = self.run_finder([[first, second]], title="Custom")
        self.assertEqual(result["outputs"]["ISSUE_NUMBER"], 3)
        self.assertEqual(len(result["calls"]), 1)

    def test_missing_issue_fails_after_last_page(self):
        result = self.run_finder([[{"title": "Other"}] * 100, []])
        self.assertEqual(result["error"], "No exercise issue found")
        self.assertEqual([call["page"] for call in result["calls"]], [1, 2])
        self.assertEqual(result["outputs"], {})

    def test_all_steps_use_local_finder(self):
        for step in range(1, 5):
            workflow = ROOT / f".github/workflows/{step}-step.yml"
            self.assertIn("uses: ./.github/workflows/find-exercise-issue.yml", workflow.read_text())


if __name__ == "__main__":
    unittest.main()
