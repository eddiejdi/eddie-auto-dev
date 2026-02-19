using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

namespace JiraClient.Tests
{
    public class JiraClientTests
    {
        private readonly string _jiraUrl = "https://your-jira-instance.atlassian.net";
        private readonly string _apiKey = "your-api-key";

        [Fact]
        public async Task SendEventAsync_WithValidData_ShouldReturnSuccess()
        {
            var jiraClient = new JiraClient(_jiraUrl, _apiKey);
            var issueKey = "ABC-123";
            var eventType = "TaskCompleted";
            var eventData = "Task ABC-123 has been completed.";

            await jiraClient.SendEventAsync(issueKey, eventType, eventData);

            // Add assertions to verify the response
        }

        [Fact]
        public async Task SendEventAsync_WithInvalidData_ShouldThrowException()
        {
            var jiraClient = new JiraClient(_jiraUrl, _apiKey);
            var issueKey = "ABC-123";
            var eventType = "TaskCompleted";
            var eventData = "";

            await Assert.ThrowsAsync<HttpRequestException>(async () => await jiraClient.SendEventAsync(issueKey, eventType, eventData));
        }

        [Fact]
        public async Task MonitorActivityAsync_WithValidData_ShouldReturnSuccess()
        {
            var jiraClient = new JiraClient(_jiraUrl, _apiKey);
            var issueKey = "ABC-123";

            await jiraClient.MonitorActivityAsync(issueKey);

            // Add assertions to verify the response
        }

        [Fact]
        public async Task MonitorActivityAsync_WithInvalidData_ShouldThrowException()
        {
            var jiraClient = new JiraClient(_jiraUrl, _apiKey);
            var issueKey = "ABC-123";

            await Assert.ThrowsAsync<HttpRequestException>(async () => await jiraClient.MonitorActivityAsync(issueKey));
        }
    }
}