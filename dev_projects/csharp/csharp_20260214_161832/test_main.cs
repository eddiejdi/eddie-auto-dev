using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_Success()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                var issue = await jiraClient.CreateIssueAsync(
                    summary: "New Task",
                    description: "This is a new task for the project.",
                    priority: "High",
                    assignee: "user1"
                );

                Assert.NotNull(issue);
                Assert.NotEmpty(issue.Id);
            }
            catch (Exception ex)
            {
                Assert.False(true, $"Error creating issue: {ex.Message}");
            }
        }

        [Fact]
        public async Task CreateIssueAsync_Error()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                await jiraClient.CreateIssueAsync(
                    summary: "",
                    description: "",
                    priority: null,
                    assignee: null
                );
            }
            catch (Exception ex)
            {
                Assert.NotNull(ex);
                Assert.Contains("summary cannot be empty", ex.Message);
                Assert.Contains("description cannot be empty", ex.Message);
                Assert.Contains("priority cannot be null", ex.Message);
                Assert.Contains("assignee cannot be null", ex.Message);
            }
        }
    }
}