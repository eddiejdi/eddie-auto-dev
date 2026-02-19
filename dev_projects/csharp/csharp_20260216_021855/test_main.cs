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
        public async Task CreateIssueAsync_WithValidCredentials_ShouldCreateIssue()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = "New task from C# Agent",
                Description = "This is a test task created by the C# Agent for tracking purposes.",
                Priority = "High",
                Status = "To Do"
            };

            // Act
            await jiraClient.CreateIssueAsync(issue);

            // Assert
            // Add assertions to verify that the issue was created successfully in Jira
        }

        [Fact]
        public async Task CreateIssueAsync_WithInvalidCredentials_ShouldThrowException()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var issue = new Issue
            {
                Summary = "New task from C# Agent",
                Description = "This is a test task created by the C# Agent for tracking purposes.",
                Priority = "High",
                Status = "To Do"
            };

            // Act and Assert
            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync(issue));
        }

        [Fact]
        public async Task CreateIssueAsync_WithNullCredentials_ShouldThrowException()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", null, "password");
            var issue = new Issue
            {
                Summary = "New task from C# Agent",
                Description = "This is a test task created by the C# Agent for tracking purposes.",
                Priority = "High",
                Status = "To Do"
            };

            // Act and Assert
            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync(issue));
        }

        [Fact]
        public async Task CreateIssueAsync_WithEmptyCredentials_ShouldThrowException()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "", "password");
            var issue = new Issue
            {
                Summary = "New task from C# Agent",
                Description = "This is a test task created by the C# Agent for tracking purposes.",
                Priority = "High",
                Status = "To Do"
            };

            // Act and Assert
            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync(issue));
        }
    }
}