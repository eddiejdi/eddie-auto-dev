using System;
using System.Net.Http;
using System.Threading.Tasks;

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
        public async Task CreateIssueAsync_WithValidInputs_ShouldSucceed()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);

            await jiraClient.CreateIssueAsync("Bug", "Test issue", "This is a test issue created by the C# Agent.");
        }

        [Fact]
        public async Task CreateIssueAsync_WithInvalidInputs_ShouldThrowException()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);

            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync("Bug", "Test issue", ""));
        }

        [Fact]
        public async Task GetIssueAsync_WithValidInputs_ShouldSucceed()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);

            await jiraClient.GetIssueAsync("TEST-1");
        }

        [Fact]
        public async Task GetIssueAsync_WithInvalidInput_ShouldThrowException()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);

            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.GetIssueAsync(""));
        }
    }
}