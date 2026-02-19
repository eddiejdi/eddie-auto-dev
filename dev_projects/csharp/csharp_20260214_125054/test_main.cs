using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestCreateIssueAsync()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Example: Create a new issue with valid data
            var issue = await jiraClient.CreateIssueAsync(
                "New Issue",
                "This is a new issue created by the CSharp Agent.",
                "bug"
            );

            Assert.NotNull(issue);
            Assert.NotEmpty(issue.Id);
        }

        [Fact]
        public async Task TestCreateIssueAsync_WithInvalidData()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Example: Create a new issue with invalid data
            try
            {
                await jiraClient.CreateIssueAsync(
                    null,
                    "",
                    ""
                );
            }
            catch (ArgumentException ex)
            {
                Assert.Contains("The value cannot be null or empty.", ex.Message);
            }
        }

        [Fact]
        public async Task TestUpdateIssueAsync()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Example: Update an existing issue with valid data
            var issue = await jiraClient.CreateIssueAsync(
                "New Issue",
                "This is a new issue created by the CSharp Agent.",
                "bug"
            );

            var updatedIssue = await jiraClient.UpdateIssueAsync(issue.Id, "Updated issue title", "This is an updated issue description.");

            Assert.NotNull(updatedIssue);
            Assert.NotEmpty(updatedIssue.Id);
        }

        [Fact]
        public async Task TestUpdateIssueAsync_WithInvalidData()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Example: Update an existing issue with invalid data
            try
            {
                await jiraClient.UpdateIssueAsync(
                    null,
                    "",
                    ""
                );
            }
            catch (ArgumentException ex)
            {
                Assert.Contains("The value cannot be null or empty.", ex.Message);
            }
        }

        [Fact]
        public async Task TestDeleteIssueAsync()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Example: Delete an existing issue with valid data
            var issue = await jiraClient.CreateIssueAsync(
                "New Issue",
                "This is a new issue created by the CSharp Agent.",
                "bug"
            );

            await jiraClient.DeleteIssueAsync(issue.Id);

            Assert.True(true);
        }

        [Fact]
        public async Task TestDeleteIssueAsync_WithInvalidData()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Example: Delete an existing issue with invalid data
            try
            {
                await jiraClient.DeleteIssueAsync(
                    null
                );
            }
            catch (ArgumentException ex)
            {
                Assert.Contains("The value cannot be null or empty.", ex.Message);
            }
        }
    }
}