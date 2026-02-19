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
        public async Task CreateIssueAsync_WithValidCredentials_ReturnsTrue()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = "New Task",
                Description = "This is a test task created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Act
            bool result = await jiraClient.CreateIssueAsync(issue);

            // Assert
            Assert.True(result, "Failed to create issue.");
        }

        [Fact]
        public async Task CreateIssueAsync_WithInvalidCredentials_ReturnsFalse()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = "New Task",
                Description = "This is a test task created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Act
            bool result = await jiraClient.CreateIssueAsync(issue);

            // Assert
            Assert.False(result, "Failed to create issue.");
        }
    }
}