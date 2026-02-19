using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            try
            {
                string jiraUrl = "https://your-jira-instance.atlassian.net";
                string username = "your-username";
                string password = "your-password";

                var client = new HttpClient();
                client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}")));

                var response = await client.GetAsync($"{jiraUrl}/rest/api/2.0/projects");
                if (response.IsSuccessStatusCode)
                {
                    Console.WriteLine("Projects fetched successfully.");
                }
                else
                {
                    Console.WriteLine($"Failed to fetch projects: {response.StatusCode}");
                }

                // Add more functionality as needed
            }
            catch (Exception ex)
            {
                Console.WriteLine($"An error occurred: {ex.Message}");
            }
        }
    }
}