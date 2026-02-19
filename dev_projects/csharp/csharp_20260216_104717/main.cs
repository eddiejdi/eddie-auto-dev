using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace JiraAgent
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

        public async Task CreateIssue(string projectKey, string issueType, string summary, string description)
        {
            var url = $"{_jiraUrl}/rest/api/2/issue";
            var content = $"{{\"fields\": {{\"project\": {{\"key\": \"{projectKey}\"}}, \"type\": {{\"name\": \"{issueType}\"}}, \"summary\": \"{summary}\", \"description\": \"{description}\"}}}}";

            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{_username}:{_password}")));
                var response = await client.PostAsync(url, new StringContent(content, Encoding.UTF8, "application/json"));

                if (response.IsSuccessStatusCode)
                {
                    Console.WriteLine("Issue created successfully.");
                }
                else
                {
                    Console.WriteLine($"Failed to create issue. Status code: {response.StatusCode}");
                }
            }
        }

        static void Main(string[] args)
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
            await jiraClient.CreateIssue("YOUR_PROJECT_KEY", "Task", "Create a new task in the project.", "This is a sample task description.");
        }
    }
}