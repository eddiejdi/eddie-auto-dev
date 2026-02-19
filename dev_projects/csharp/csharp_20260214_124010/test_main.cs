using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace JiraSharp.Tests
{
    public class JiraClientTests
    {
        [Fact]
        public async Task LoginAsync_WithValidCredentials_ShouldSucceed()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
            await jiraClient.LoginAsync();
            Assert.True(jiraClient.IsLoggedIn);
        }

        [Fact]
        public async Task LoginAsync_WithInvalidCredentials_ShouldFail()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "invalid-username", "invalid-api-token");
            await jiraClient.LoginAsync();
            Assert.False(jiraClient.IsLoggedIn);
        }

        [Fact]
        public async Task CreateIssueAsync_WithValidData_ShouldSucceed()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
            await jiraClient.LoginAsync();

            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent.",
                ProjectKey = "YOUR-PROJECT-KEY"
            };

            var createdIssue = await jiraClient.CreateIssueAsync(issue);
            Assert.NotNull(createdIssue);
        }

        [Fact]
        public async Task CreateIssueAsync_WithInvalidData_ShouldFail()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
            await jiraClient.LoginAsync();

            var issue = new Issue
            {
                Summary = null,
                Description = "This is a test issue created by the C# Agent.",
                ProjectKey = "YOUR-PROJECT-KEY"
            };

            await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.CreateIssueAsync(issue));
        }

        [Fact]
        public async Task UpdateIssueAsync_WithValidData_ShouldSucceed()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
            await jiraClient.LoginAsync();

            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent.",
                ProjectKey = "YOUR-PROJECT-KEY"
            };

            await jiraClient.CreateIssueAsync(issue);

            var update = new IssueUpdate
            {
                Description = "This is an updated test issue."
            };

            var updatedIssue = await jiraClient.UpdateIssueAsync(issue.Key, update);
            Assert.NotNull(updatedIssue);
        }

        [Fact]
        public async Task UpdateIssueAsync_WithInvalidData_ShouldFail()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
            await jiraClient.LoginAsync();

            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = null,
                ProjectKey = "YOUR-PROJECT-KEY"
            };

            await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.UpdateIssueAsync(issue.Key, update));
        }

        [Fact]
        public async Task DeleteIssueAsync_WithValidData_ShouldSucceed()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
            await jiraClient.LoginAsync();

            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent.",
                ProjectKey = "YOUR-PROJECT-KEY"
            };

            await jiraClient.CreateIssueAsync(issue);

            await jiraClient.DeleteIssueAsync(issue.Key);
        }

        [Fact]
        public async Task DeleteIssueAsync_WithInvalidData_ShouldFail()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
            await jiraClient.LoginAsync();

            var issueKey = "INVALID-KEY";

            await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.DeleteIssueAsync(issueKey));
        }
    }
}