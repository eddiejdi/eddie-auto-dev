using System;
using System.Net.Http;
using System.Text.Json;
using JiraSharpClient;
using Xunit;

namespace JiraSharpClient.Tests
{
    public class JiraClientTests
    {
        [Fact]
        public async Task CreateProjectAsync_Success()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Create a new project
            var project = await client.Projects.CreateAsync(new ProjectCreateRequest
            {
                Key = "PRJ1",
                Name = "My Project"
            });

            Assert.NotNull(project);
            Assert.NotEmpty(project.Key);
        }

        [Fact]
        public async Task CreateIssueAsync_Success()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Create a new issue
            var issue = await client.Issues.CreateAsync(new IssueCreateRequest
            {
                ProjectKey = "PRJ1",
                Summary = "Test Issue",
                Description = "This is a test issue for the C# Agent integration."
            });

            Assert.NotNull(issue);
            Assert.NotEmpty(issue.Id);
        }

        [Fact]
        public async Task LogAsync_Success()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Create a new project
            var project = await client.Projects.CreateAsync(new ProjectCreateRequest
            {
                Key = "PRJ1",
                Name = "My Project"
            });

            // Create a new issue
            var issue = await client.Issues.CreateAsync(new IssueCreateRequest
            {
                ProjectKey = project.Key,
                Summary = "Test Issue",
                Description = "This is a test issue for the C# Agent integration."
            });

            // Log a message to Jira
            await client.Logs.CreateAsync(new LogCreateRequest
            {
                ProjectKey = project.Key,
                IssueId = issue.Id,
                Message = "This is a test log entry from the C# Agent integration."
            });

            Assert.NotNull(issue);
            Assert.NotEmpty(issue.Id);
        }
    }
}