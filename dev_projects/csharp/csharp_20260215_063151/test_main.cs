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
        public async Task MonitorTask_ValidTaskId_ReturnsStatusName()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var taskId = "Task1";

            var task = await client.GetIssueAsync(taskId);

            Assert.Equal("Open", task.Fields.Status.Name);
        }

        [Fact]
        public async Task MonitorTask_InvalidTaskId_ThrowsException()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var taskId = "InvalidTask";

            await Assert.ThrowsAsync<Exception>(async () => await client.GetIssueAsync(taskId));
        }

        [Fact]
        public async Task MonitorTask_TaskWithNoStatus_ReturnsDefaultStatusName()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var taskId = "TaskWithoutStatus";

            var task = await client.GetIssueAsync(taskId);

            Assert.Equal("Open", task.Fields.Status.Name);
        }
    }
}