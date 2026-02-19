using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

namespace JiraIntegration.Tests
{
    public class JiraClientTests
    {
        private readonly string _jiraUrl = "https://your-jira-instance.atlassian.net";
        private readonly string _username = "your-username";
        private readonly string _password;

        public JiraClientTests()
        {
            _jiraUrl = "https://your-jira-instance.atlassian.net";
            _username = "your-username";
            _password = "your-password";
        }

        [Fact]
        public async Task CreateIssueAsync_Successful()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);

            await jiraClient.CreateIssueAsync("Bug", "Test case failed", "Fix the bug");

            // Add assertions here if needed
        }

        [Fact]
        public async Task CreateIssueAsync_InvalidParameters()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);

            await Assert.ThrowsAsync<HttpRequestException>(async () =>
                await jiraClient.CreateIssueAsync("Bug", "", ""));
        }

        [Fact]
        public async Task CreateIssueAsync_InvalidCredentials()
        {
            var jiraClient = new JiraClient(_jiraUrl, "invalid-username", "invalid-password");

            await Assert.ThrowsAsync<HttpRequestException>(async () =>
                await jiraClient.CreateIssueAsync("Bug", "Test case failed", "Fix the bug"));
        }
    }
}