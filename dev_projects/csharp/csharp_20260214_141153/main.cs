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
            var client = new HttpClient();
            var content = new FormUrlEncodedContent(new[]
            {
                new KeyValuePair<string, string>("fields[issueTypeId]", issueType),
                new KeyValuePair<string, string>("fields[summary]", summary),
                new KeyValuePair<string, string>("fields[description]", description)
            });

            var response = await client.PostAsync($"{_jiraUrl}/rest/api/2/issue", content);
            response.EnsureSuccessStatusCode();
        }
    }

    class Program
    {
        static async Task Main(string[] args)
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                await jiraClient.CreateIssueAsync("Bug", "Test case 1 failed", "Fix the bug");
                Console.WriteLine("Issue created successfully.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"An error occurred: {ex.Message}");
            }
        }
    }
}