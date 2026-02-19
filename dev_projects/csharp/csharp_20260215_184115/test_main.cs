using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssue_Success()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 },
                Assignee = new User { Name = "your-username" }
            };

            var createdIssue = await jiraClient.CreateIssue(issue);

            Assert.NotNull(createdIssue);
        }

        [Fact]
        public async Task CreateIssue_Error_InvalidSummary()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue with an invalid summary
            var issue = new Issue
            {
                Summary = "",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 },
                Assignee = new User { Name = "your-username" }
            };

            await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.CreateIssue(issue));
        }

        [Fact]
        public async Task UpdateIssue_Success()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 },
                Assignee = new User { Name = "your-username" }
            };

            var createdIssue = await jiraClient.CreateIssue(issue);

            // Update the issue
            issue.Status = new Status { Id = 2 }; // In Progress

            await jiraClient.UpdateIssue(createdIssue.Key, issue);

            Assert.NotNull(createdIssue);
        }

        [Fact]
        public async Task UpdateIssue_Error_InvalidStatusId()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 },
                Assignee = new User { Name = "your-username" }
            };

            var createdIssue = await jiraClient.CreateIssue(issue);

            // Update the issue with an invalid status ID
            issue.Status = new Status { Id = -1 }; // Invalid status ID

            await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.UpdateIssue(createdIssue.Key, issue));
        }

        [Fact]
        public async Task CloseIssue_Success()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 },
                Assignee = new User { Name = "your-username" }
            };

            var createdIssue = await jiraClient.CreateIssue(issue);

            // Close the issue
            issue.Status = new Status { Id = 3 }; // Closed

            await jiraClient.CloseIssue(createdIssue.Key, issue);

            Assert.NotNull(createdIssue);
        }

        [Fact]
        public async Task CloseIssue_Error_InvalidStatusId()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "Test Issue",
                Description = "This is a test issue created by the C# Agent for Jira integration.",
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 },
                Assignee = new User { Name = "your-username" }
            };

            var createdIssue = await jiraClient.CreateIssue(issue);

            // Close the issue with an invalid status ID
            issue.Status = new Status { Id = -1 }; // Invalid status ID

            await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.CloseIssue(createdIssue.Key, issue));
        }
    }
}