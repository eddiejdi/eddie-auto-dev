using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace YourNamespace.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_WithValidData_ShouldSucceed()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = "New Feature Request",
                Description = "Implement a new feature in the application.",
                ProjectKey = "YOUR-PROJECT-KEY"
            };

            // Act
            await jiraClient.CreateIssueAsync(issue);

            // Assert
            // Add assertions here to verify that the issue was created successfully
        }

        [Fact]
        public async Task CreateIssueAsync_WithInvalidData_ShouldThrowException()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = null,
                Description = "",
                ProjectKey = ""
            };

            // Act and Assert
            await Task.Run(() => jiraClient.CreateIssueAsync(issue)).ShouldThrowExactly(typeof(Exception));
        }
    }
}