using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;
using Xunit;

namespace Scrum14Agent.Tests
{
    public class ProgramTests
    {
        private readonly JiraClient _jiraClient;

        public ProgramTests()
        {
            _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        }

        [Fact]
        public async Task CreateIssueAsync_ShouldCreateNewIssue()
        {
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "New Scrum 14 Task",
                Description = "This is a new task for the Scrum 14 project.",
                Priority = "High"
            };

            await _jiraClient.CreateIssueAsync(issue);

            var createdIssue = await _jiraClient.GetIssueAsync(issue.Id);
            Assert.NotNull(createdIssue);
        }

        [Fact]
        public async Task GetIssuesAsync_ShouldReturnAllIssuesInProject()
        {
            var issues = await _jiraClient.GetIssuesAsync("YOUR_PROJECT_KEY");
            Assert.NotEmpty(issues);
        }

        [Fact]
        public async Task UpdateIssueAsync_ShouldUpdateExistingIssue()
        {
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "New Scrum 14 Task",
                Description = "This is a new task for the Scrum 14 project.",
                Priority = "High"
            };

            await _jiraClient.CreateIssueAsync(issue);

            var update = new IssueUpdate
            {
                Description = "This is an updated description for the Scrum 14 task."
            };

            await _jiraClient.UpdateIssueAsync(issue.Id, update);

            var updatedIssue = await _jiraClient.GetIssueAsync(issue.Id);
            Assert.NotNull(updatedIssue);
        }

        [Fact]
        public async Task DeleteIssueAsync_ShouldDeleteExistingIssue()
        {
            var issue = new Issue
            {
                ProjectKey = "YOUR_PROJECT_KEY",
                Summary = "New Scrum 14 Task",
                Description = "This is a new task for the Scrum 14 project.",
                Priority = "High"
            };

            await _jiraClient.CreateIssueAsync(issue);

            await _jiraClient.DeleteIssueAsync(issue.Id);
        }
    }
}