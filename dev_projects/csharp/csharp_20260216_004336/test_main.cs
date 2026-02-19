using System;
using System.Net.Http;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestCreateTask()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Criar uma nova tarefa com valores válidos
            var task = new Task
            {
                Summary = "Teste da Integração",
                Description = "Integrando C# Agent com Jira",
                Assignee = client.Users.Get("user-id"),
                Priority = client.Priorities.Get("high")
            };

            // Adicionar a tarefa ao projeto
            var project = client.Projects.Get("project-id");
            await task.CreateAsync(project);

            Assert.True(task.Id > 0, "Tarefa criada com sucesso!");
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidSummary()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Criar uma nova tarefa com um summary inválido
            var task = new Task
            {
                Summary = "",
                Description = "Integrando C# Agent com Jira",
                Assignee = client.Users.Get("user-id"),
                Priority = client.Priorities.Get("high")
            };

            // Adicionar a tarefa ao projeto
            var project = client.Projects.Get("project-id");
            await task.CreateAsync(project);

            Assert.False(task.Id > 0, "Tarefa criada com sucesso!");
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidDescription()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Criar uma nova tarefa com uma description inválida
            var task = new Task
            {
                Summary = "Teste da Integração",
                Description = "",
                Assignee = client.Users.Get("user-id"),
                Priority = client.Priorities.Get("high")
            };

            // Adicionar a tarefa ao projeto
            var project = client.Projects.Get("project-id");
            await task.CreateAsync(project);

            Assert.False(task.Id > 0, "Tarefa criada com sucesso!");
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidAssignee()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Criar uma nova tarefa com um assignee inválido
            var task = new Task
            {
                Summary = "Teste da Integração",
                Description = "Integrando C# Agent com Jira",
                Assignee = null,
                Priority = client.Priorities.Get("high")
            };

            // Adicionar a tarefa ao projeto
            var project = client.Projects.Get("project-id");
            await task.CreateAsync(project);

            Assert.False(task.Id > 0, "Tarefa criada com sucesso!");
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidPriority()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Criar uma nova tarefa com uma priority inválida
            var task = new Task
            {
                Summary = "Teste da Integração",
                Description = "Integrando C# Agent com Jira",
                Assignee = client.Users.Get("user-id"),
                Priority = null
            };

            // Adicionar a tarefa ao projeto
            var project = client.Projects.Get("project-id");
            await task.CreateAsync(project);

            Assert.False(task.Id > 0, "Tarefa criada com sucesso!");
        }
    }
}