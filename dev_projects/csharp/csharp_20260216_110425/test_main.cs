using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

namespace CSharpAgent.JiraIntegration.Tests
{
    public class ProgramTests
    {
        private readonly JiraClient _jiraClient;

        public ProgramTests()
        {
            _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
        }

        [Fact]
        public async Task TestAddTaskWithValidData()
        {
            var task = new Task
            {
                Summary = "Implementar o CSharp Agent",
                Description = "Integração com ASP.NET Core, Entity Framework Core, LINQ e async/await",
                Assignee = "YourUsername"
            };

            await _jiraClient.Tasks.AddAsync(task);

            Assert.True(task.Id > 0);
        }

        [Fact]
        public async Task TestAddTaskWithInvalidData()
        {
            var task = new Task
            {
                Summary = "",
                Description = "Integração com ASP.NET Core, Entity Framework Core, LINQ e async/await",
                Assignee = ""
            };

            await Assert.ThrowsAsync<ArgumentException>(() => _jiraClient.Tasks.AddAsync(task));
        }
    }
}