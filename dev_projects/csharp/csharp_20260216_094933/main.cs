using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace JiraAgent
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var client = new HttpClient();
            var url = "https://your-jira-instance.atlassian.net/rest/api/3/issue/{issueId}/comment";

            try
            {
                var response = await client.GetAsync(url);
                response.EnsureSuccessStatusCode();

                var comment = await response.Content.ReadAsStringAsync();
                Console.WriteLine(comment);
            }
            catch (HttpRequestException ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }
        }
    }
}