using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

namespace JiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestGetAsync_Success()
        {
            var client = new HttpClient();
            var response = await client.GetAsync("https://your-jira-instance.atlassian.net/rest/api/2.0/search?jql=project=YOUR_PROJECT&fields=summary,status");
            response.EnsureSuccessStatusCode();

            var responseBody = await response.Content.ReadAsStringAsync();
            Assert.NotEmpty(responseBody);
        }

        [Fact]
        public async Task TestGetAsync_Error()
        {
            var client = new HttpClient();
            var response = await client.GetAsync("https://your-jira-instance.atlassian.net/rest/api/2.0/search?jql=project=YOUR_PROJECT&fields=summary,status");
            Assert.Equal(404, (int)response.StatusCode);
        }

        [Fact]
        public async Task TestGetAsync_InvalidJQL()
        {
            var client = new HttpClient();
            var response = await client.GetAsync("https://your-jira-instance.atlassian.net/rest/api/2.0/search?jql=project=YOUR_PROJECT&fields=summary,status");
            Assert.Equal(400, (int)response.StatusCode);
        }
    }
}