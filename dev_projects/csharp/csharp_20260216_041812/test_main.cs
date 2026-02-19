using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssue_Successfully()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Create a new issue with valid data
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "Test issue",
                Description = "This is a test issue created by C# Agent.",
                Priority = Priority.High,
                Status = Status.Open
            };

            await jiraClient.CreateIssue(issue);

            // Assert that the issue was created successfully
            var createdIssue = await jiraClient.GetIssue(issue.Key);
            Assert.NotNull(createdIssue);
        }

        [Fact]
        public async Task CreateIssue_ThrowsException_WhenProjectKeyIsInvalid()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Attempt to create an issue with an invalid project key
            var issue = new Issue
            {
                ProjectKey = "INVALID_PROJECT_KEY",
                Summary = "Test issue",
                Description = "This is a test issue created by C# Agent.",
                Priority = Priority.High,
                Status = Status.Open
            };

            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssue(issue));
        }

        [Fact]
        public async Task CreateIssue_ThrowsException_WhenSummaryIsInvalid()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Attempt to create an issue with an invalid summary
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "",
                Description = "This is a test issue created by C# Agent.",
                Priority = Priority.High,
                Status = Status.Open
            };

            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssue(issue));
        }

        [Fact]
        public async Task CreateIssue_ThrowsException_WhenDescriptionIsInvalid()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Attempt to create an issue with an invalid description
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "Test issue",
                Description = "",
                Priority = Priority.High,
                Status = Status.Open
            };

            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssue(issue));
        }

        [Fact]
        public async Task CreateIssue_ThrowsException_WhenPriorityIsInvalid()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Attempt to create an issue with an invalid priority
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "Test issue",
                Description = "This is a test issue created by C# Agent.",
                Priority = (Priority)99, // Invalid value
                Status = Status.Open
            };

            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssue(issue));
        }

        [Fact]
        public async Task CreateIssue_ThrowsException_WhenStatusIsInvalid()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Attempt to create an issue with an invalid status
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "Test issue",
                Description = "This is a test issue created by C# Agent.",
                Priority = Priority.High,
                Status = (Status)99, // Invalid value
            };

            await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssue(issue));
        }
    }
}