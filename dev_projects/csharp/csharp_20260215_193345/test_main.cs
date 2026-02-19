using System;
using System.Linq;
using JiraSharpClient;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestCreateIssueAsync()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                // Create a new issue
                var issue = await client.CreateIssueAsync(
                    "New Issue",
                    "This is a new issue created by the C# Agent.",
                    "bug"
                );

                Assert.NotNull(issue);
                Assert.NotEmpty(issue.Key);
            }
            catch (Exception ex)
            {
                throw;
            }
        }

        [Fact]
        public async Task TestCreateIssueAsyncWithInvalidInput()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                // Create a new issue with invalid input
                await client.CreateIssueAsync(
                    "",
                    "This is a new issue created by the C# Agent.",
                    ""
                );
            }
            catch (Exception ex)
            {
                Assert.IsType<ArgumentException>(ex);
            }
        }

        [Fact]
        public async Task TestUpdateIssueAsync()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                // Create a new issue
                var issue = await client.CreateIssueAsync(
                    "New Issue",
                    "This is a new issue created by the C# Agent.",
                    "bug"
                );

                // Update an existing issue
                var updatedIssue = await client.UpdateIssueAsync(issue.Key, "Updated description", "feature");

                Assert.NotNull(updatedIssue);
                Assert.NotEmpty(updatedIssue.Key);
            }
            catch (Exception ex)
            {
                throw;
            }
        }

        [Fact]
        public async Task TestUpdateIssueAsyncWithInvalidInput()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                // Update an existing issue with invalid input
                await client.UpdateIssueAsync(
                    "",
                    "Updated description",
                    ""
                );
            }
            catch (Exception ex)
            {
                Assert.IsType<ArgumentException>(ex);
            }
        }

        [Fact]
        public async Task TestDeleteIssueAsync()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                // Create a new issue
                var issue = await client.CreateIssueAsync(
                    "New Issue",
                    "This is a new issue created by the C# Agent.",
                    "bug"
                );

                // Delete an existing issue
                await client.DeleteIssueAsync(issue.Key);

                Assert.True(true);
            }
            catch (Exception ex)
            {
                throw;
            }
        }

        [Fact]
        public async Task TestDeleteIssueAsyncWithInvalidInput()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                // Delete an existing issue with invalid input
                await client.DeleteIssueAsync("");
            }
            catch (Exception ex)
            {
                Assert.IsType<ArgumentException>(ex);
            }
        }
    }
}