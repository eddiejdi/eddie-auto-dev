using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharpClient;
using Xunit;

namespace JiraSharpClient.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestCreateTaskWithValidData()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var project = client.Projects.Get("project-id");

            var task = new Task
            {
                Summary = "Implementar o C# Agent com Jira",
                Description = "Integrar C# Agent com Jira para tracking de atividades",
                Assignee = client.Users.Get("assignee-username"),
                Priority = client.Priorities.Get("high")
            };

            await task.Create(project);

            Assert.True(task.Key != null);
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidData()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var project = client.Projects.Get("project-id");

            var task = new Task
            {
                Summary = "",
                Description = null,
                Assignee = null,
                Priority = null
            };

            await Assert.ThrowsAsync<ArgumentException>(() => task.Create(project));
        }
    }
}