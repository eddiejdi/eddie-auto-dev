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
                var client = new HttpClient();
                var url = "http://your-jira-server/rest/api/2/issue";

                // Simula um issue para teste
                var issueData = new
                {
                    fields = new
                    {
                        project = new { key = "YOUR_PROJECT_KEY" },
                        summary = "Test Issue",
                        description = "This is a test issue created by CSharpAgentJiraIntegration.",
                        issuetype = new { name = "Bug" }
                    }
                };

                var response = await client.PostAsJsonAsync(url, issueData);

                if (response.IsSuccessStatusCode)
                {
                    Console.WriteLine("Issue created successfully.");
                }
                else
                {
                    Console.WriteLine($"Failed to create issue. Status code: {response.StatusCode}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"An error occurred: {ex.Message}");
            }
        }
    }
}