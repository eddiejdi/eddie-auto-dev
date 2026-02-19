using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace JiraIntegration
{
    public class JiraService
    {
        private readonly string _jiraUrl;
        private readonly string _username;
        private readonly string _password;

        public JiraService(string jiraUrl, string username, string password)
        {
            _jiraUrl = jiraUrl;
            _username = username;
            _password = password;
        }

        public async Task CreateIssueAsync(string summary, string description)
        {
            var requestUri = $"{_jiraUrl}/rest/api/2/issue";
            var requestBody = new
            {
                fields = new
                {
                    project = new { key = "YOUR_PROJECT_KEY" },
                    summary = summary,
                    description = description,
                    issuetype = new { name = "Bug" }
                }
            };

            using (var client = new System.Net.Http.HttpClient())
            {
                var content = new System.Text.Json.JsonContent(requestBody);
                var response = await client.PostAsync(requestUri, content);

                if (!response.IsSuccessStatusCode)
                {
                    throw new Exception($"Failed to create issue: {await response.Content.ReadAsStringAsync()}");
                }
            }
        }

        public async Task GetIssuesAsync(string projectKey)
        {
            var requestUri = $"{_jiraUrl}/rest/api/2/search?jql=project={projectKey}";
            using (var client = new System.Net.Http.HttpClient())
            {
                var response = await client.GetAsync(requestUri);

                if (!response.IsSuccessStatusCode)
                {
                    throw new Exception($"Failed to get issues: {await response.Content.ReadAsStringAsync()}");
                }

                var responseBody = await response.Content.ReadAsStringAsync();
                // Parse the JSON response and process it as needed
            }
        }
    }

    class Program
    {
        static async Task Main(string[] args)
        {
            var jiraService = new JiraService("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            await jiraService.CreateIssueAsync("Bug in the application", "The application crashes when trying to access a specific feature.");

            var issues = await jiraService.GetIssuesAsync("YOUR_PROJECT_KEY");
            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue ID: {issue.id}, Summary: {issue.fields.summary}");
            }
        }
    }
}