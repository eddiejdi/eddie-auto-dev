using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestFetchProjectsSuccess()
        {
            // Arrange
            string jiraUrl = "https://your-jira-instance.atlassian.net";
            string username = "your-username";
            string password = "your-password";

            var client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}")));

            // Act
            var response = await client.GetAsync($"{jiraUrl}/rest/api/2.0/projects");

            // Assert
            Assert.True(response.IsSuccessStatusCode);
        }

        [Fact]
        public async Task TestFetchProjectsFailure()
        {
            // Arrange
            string jiraUrl = "https://your-jira-instance.atlassian.net";
            string username = "your-username";
            string password = "your-password";

            var client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}")));

            // Act
            var response = await client.GetAsync($"{jiraUrl}/rest/api/2.0/projects");

            // Assert
            Assert.False(response.IsSuccessStatusCode);
        }

        [Fact]
        public async Task TestFetchProjectsWithInvalidCredentials()
        {
            // Arrange
            string jiraUrl = "https://your-jira-instance.atlassian.net";
            string username = "invalid-username";
            string password = "invalid-password";

            var client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{username}:{password}")));

            // Act
            var response = await client.GetAsync($"{jiraUrl}/rest/api/2.0/projects");

            // Assert
            Assert.False(response.IsSuccessStatusCode);
        }
    }
}