using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

namespace JiraAgent.Tests
{
    public class JiraClientTests
    {
        private readonly string _jiraUrl = "https://your-jira-instance.atlassian.net";
        private readonly string _username = "your-username";
        private readonly string _password = "your-password";

        [Fact]
        public async Task CreateIssue_WithValidInputs_ShouldCreateIssueSuccessfully()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);
            await jiraClient.CreateIssue("YOUR_PROJECT_KEY", "Task", "Create a new task in the project.", "This is a sample task description.");

            // Add assertions to verify that the issue was created successfully
        }

        [Fact]
        public async Task CreateIssue_WithInvalidInputs_ShouldThrowException()
        {
            var jiraClient = new JiraClient(_jiraUrl, _username, _password);
            await Assert.ThrowsAsync<HttpRequestException>(async () => await jiraClient.CreateIssue("YOUR_PROJECT_KEY", "Task", "Create a new task in the project.", ""));
        }
    }
}