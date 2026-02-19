using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_ReturnsTrue_WhenValidCredentialsAndIssueDataAreProvided()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = "New issue created by C# Agent",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Act
            bool result = await jiraClient.CreateIssueAsync(issue);

            // Assert
            Assert.True(result);
        }

        [Fact]
        public async Task CreateIssueAsync_ReturnsFalse_WhenInvalidCredentialsAreProvided()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "invalidpassword");
            var issue = new Issue
            {
                Summary = "New issue created by C# Agent",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Act
            bool result = await jiraClient.CreateIssueAsync(issue);

            // Assert
            Assert.False(result);
        }

        [Fact]
        public async Task CreateIssueAsync_ReturnsFalse_WhenInvalidProjectKeyIsProvided()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = "New issue created by C# Agent",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "INVALID_PROJECT_KEY"
            };

            // Act
            bool result = await jiraClient.CreateIssueAsync(issue);

            // Assert
            Assert.False(result);
        }
    }
}