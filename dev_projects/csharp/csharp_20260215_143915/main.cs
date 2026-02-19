using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace JiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            try
            {
                var client = new HttpClient();
                var response = await client.GetAsync("https://your-jira-instance.atlassian.net/rest/api/2.0/search?jql=project=YOUR_PROJECT&fields=summary,status");
                response.EnsureSuccessStatusCode();

                var responseBody = await response.Content.ReadAsStringAsync();
                Console.WriteLine(responseBody);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"An error occurred: {ex.Message}");
            }
        }
    }
}