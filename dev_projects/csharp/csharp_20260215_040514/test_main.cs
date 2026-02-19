using System;
using System.Threading.Tasks;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueSuccess()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
            var issue = new Issue
            {
                Summary = "New task",
                Description = "This is a new task created by CSharpAgentJiraIntegration",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Act
            var createdIssue = await jiraClient.CreateIssueAsync(issue);

            // Assert
            Assert.NotNull(createdIssue);
            Assert.NotEmpty(createdIssue.Key);
        }

        [Fact]
        public async Task CreateIssueFailure()
        {
            // Arrange
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
            var issue = new Issue
            {
                Summary = "",
                Description = "This is a new task created by CSharpAgentJiraIntegration",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Act
            var createdIssue = await jiraClient.CreateIssueAsync(issue);

            // Assert
            Assert.Null(createdIssue);
        }
    }
}