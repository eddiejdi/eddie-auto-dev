using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net/rest/api/3", "your-username", "your-password");

            try
            {
                // Create a new issue
                var issue = new Issue
                {
                    Fields = new IssueFields
                    {
                        Project = new Project { Key = "YOUR_PROJECT_KEY" },
                        Summary = "Test Issue",
                        Description = "This is a test issue created by the CSharp Agent Jira Integration.",
                        Priority = new Priority { Name = "High" },
                        Status = new Status { Name = "To Do" }
                    }
                };

                var response = await jiraClient.Issue.CreateAsync(issue);

                Console.WriteLine($"Issue created with ID: {response.Id}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error creating issue: {ex.Message}");
            }
        }
    }

    class JiraClient
    {
        private readonly string _baseUrl;
        private readonly string _username;
        private readonly string _password;

        public JiraClient(string baseUrl, string username, string password)
        {
            _baseUrl = baseUrl;
            _username = username;
            _password = password;
        }

        public async Task<T> CreateAsync<T>(T entity)
        {
            using (var httpClient = new HttpClient())
            {
                var content = new StringContent(JsonSerializer.Serialize(entity), Encoding.UTF8, "application/json");
                content.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.ASCII.GetBytes($"{_username}:{_password}")));

                var response = await httpClient.PostAsync($"{_baseUrl}/issue", content);

                if (response.IsSuccessStatusCode)
                {
                    var responseBody = await response.Content.ReadAsStringAsync();
                    return JsonSerializer.Deserialize<T>(responseBody);
                }
                else
                {
                    throw new Exception($"Failed to create issue. Status code: {response.StatusCode}");
                }
            }
        }
    }

    class Issue
    {
        public Fields Fields { get; set; }
    }

    class IssueFields
    {
        public Project Project { get; set; }
        public Summary Summary { get; set; }
        public Description Description { get; set; }
        public Priority Priority { get; set; }
        public Status Status { get; set; }
    }

    class Project
    {
        public string Key { get; set; }
    }

    class Priority
    {
        public string Name { get; set; }
    }

    class Status
    {
        public string Name { get; set; }
    }
}