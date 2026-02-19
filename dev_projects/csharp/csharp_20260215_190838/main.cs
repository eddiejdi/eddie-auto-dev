using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace JiraIntegration
{
    public class JiraClient
    {
        private readonly string _jiraUrl;
        private readonly string _username;
        private readonly string _password;

        public JiraClient(string jiraUrl, string username, string password)
        {
            _jiraUrl = jiraUrl;
            _username = username;
            _password = password;
        }

        public async Task CreateIssueAsync(string issueType, string summary, string description)
        {
            var url = $"{_jiraUrl}/rest/api/2/issue";
            var content = $"{{\"fields\": {{\"project\": {{\"key\": \"{issueType}\"}}, \"summary\": \"{summary}\", \"description\": \"{description}\"}}}}";

            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes($"{_username}:{_password}")));

                var response = await client.PostAsync(url, new StringContent(content, System.Text.Encoding.UTF8, "application/json"));

                if (!response.IsSuccessStatusCode)
                {
                    throw new Exception($"Failed to create issue: {await response.Content.ReadAsStringAsync()}");
                }
            }
        }

        public async Task GetIssueAsync(string issueKey)
        {
            var url = $"{_jiraUrl}/rest/api/2/issue/{issueKey}";
            using (var client = new HttpClient())
            {
                var response = await client.GetAsync(url);

                if (!response.IsSuccessStatusCode)
                {
                    throw new Exception($"Failed to get issue: {await response.Content.ReadAsStringAsync()}");
                }

                Console.WriteLine(await response.Content.ReadAsStringAsync());
            }
        }
    }

    class Program
    {
        static async Task Main(string[] args)
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            await jiraClient.CreateIssueAsync("Bug", "Test issue", "This is a test issue created by the C# Agent.");
            await jiraClient.GetIssueAsync("TEST-1");
        }
    }
}