using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace JiraScrum14
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var jiraClient = new HttpClient();
            var projectKey = "YOUR_PROJECT_KEY";
            var issueId = "YOUR_ISSUE_ID";

            try
            {
                // Fetch the issue details from Jira
                var response = await jiraClient.GetAsync($"rest/api/2/issue/{issueId}");
                var issue = await response.Content.ReadAsStringAsync();

                Console.WriteLine("Issue Details:");
                Console.WriteLine(issue);

                // Update the status of the issue in Jira
                var updateRequest = new
                {
                    fields = new
                    {
                        status = new { id = "10001" } // Assuming 'In Progress' is ID 10001
                    }
                };

                var updateResponse = await jiraClient.PutAsync($"rest/api/2/issue/{issueId}", new StringContent(JsonConvert.SerializeObject(updateRequest), System.Text.Encoding.UTF8, "application/json"));

                Console.WriteLine("Issue Status Updated:");
                Console.WriteLine(await updateResponse.Content.ReadAsStringAsync());
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
            }
        }
    }

    class JiraClient
    {
        private readonly HttpClient _httpClient;

        public JiraClient(HttpClient httpClient)
        {
            _httpClient = httpClient;
        }

        public async Task<T> GetAsync(string url)
        {
            var response = await _httpClient.GetAsync(url);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsAsync<T>();
        }
    }
}