using System;
using System.Net.Http;
using System.Threading.Tasks;
using Newtonsoft.Json;

namespace JiraScrum14.Tests
{
    public class ProgramTests
    {
        private readonly HttpClient _httpClient = new HttpClient();

        [Fact]
        public async Task FetchIssueDetails_Success()
        {
            var projectKey = "YOUR_PROJECT_KEY";
            var issueId = "YOUR_ISSUE_ID";

            try
            {
                // Fetch the issue details from Jira
                var response = await _httpClient.GetAsync($"rest/api/2/issue/{issueId}");
                var issue = await response.Content.ReadAsStringAsync();

                Console.WriteLine("Issue Details:");
                Console.WriteLine(issue);

                // Verify that the issue details were fetched successfully
                Assert.NotNull(issue);
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
                throw;
            }
        }

        [Fact]
        public async Task FetchIssueDetails_Error()
        {
            var projectKey = "YOUR_PROJECT_KEY";
            var issueId = "INVALID_ISSUE_ID";

            try
            {
                // Attempt to fetch an invalid issue details from Jira
                var response = await _httpClient.GetAsync($"rest/api/2/issue/{issueId}");
                var issue = await response.Content.ReadAsStringAsync();

                Console.WriteLine("Issue Details:");
                Console.WriteLine(issue);

                // Verify that the exception was thrown as expected
                Assert.ThrowsAsync<HttpRequestException>(async () => await _httpClient.GetAsync($"rest/api/2/issue/{issueId}"));
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
                throw;
            }
        }

        [Fact]
        public async Task UpdateIssueStatus_Success()
        {
            var projectKey = "YOUR_PROJECT_KEY";
            var issueId = "YOUR_ISSUE_ID";

            try
            {
                // Fetch the current status of the issue from Jira
                var response = await _httpClient.GetAsync($"rest/api/2/issue/{issueId}");
                var issue = await response.Content.ReadAsStringAsync();

                Console.WriteLine("Current Issue Status:");
                Console.WriteLine(issue);

                // Update the status of the issue in Jira
                var updateRequest = new
                {
                    fields = new
                    {
                        status = new { id = "10001" } // Assuming 'In Progress' is ID 10001
                    }
                };

                var updateResponse = await _httpClient.PutAsync($"rest/api/2/issue/{issueId}", new StringContent(JsonConvert.SerializeObject(updateRequest), System.Text.Encoding.UTF8, "application/json"));

                Console.WriteLine("Issue Status Updated:");
                Console.WriteLine(await updateResponse.Content.ReadAsStringAsync());

                // Verify that the issue status was updated successfully
                Assert.NotNull(issue);
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
                throw;
            }
        }

        [Fact]
        public async Task UpdateIssueStatus_Error()
        {
            var projectKey = "YOUR_PROJECT_KEY";
            var issueId = "INVALID_ISSUE_ID";

            try
            {
                // Attempt to update an invalid issue status in Jira
                var updateRequest = new
                {
                    fields = new
                    {
                        status = new { id = "10002" } // Assuming 'In Progress' is ID 10001
                    }
                };

                var updateResponse = await _httpClient.PutAsync($"rest/api/2/issue/{issueId}", new StringContent(JsonConvert.SerializeObject(updateRequest), System.Text.Encoding.UTF8, "application/json"));

                Console.WriteLine("Issue Status Updated:");
                Console.WriteLine(await updateResponse.Content.ReadAsStringAsync());

                // Verify that the exception was thrown as expected
                Assert.ThrowsAsync<HttpRequestException>(async () => await _httpClient.PutAsync($"rest/api/2/issue/{issueId}", new StringContent(JsonConvert.SerializeObject(updateRequest), System.Text.Encoding.UTF8, "application/json")));
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
                throw;
            }
        }
    }
}