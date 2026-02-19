using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateTaskAsync_WithValidData_ShouldCreateTask()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            await CreateTaskAsync("Implement C# Agent", "This is a test task for implementing the C# Agent.");

            // Verificar se o tarefa foi criada corretamente
        }

        [Fact]
        public async Task CreateTaskAsync_WithInvalidData_ShouldThrowException()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Tentar criar uma tarefa com valores inválidos
            await Assert.ThrowsAsync<ArgumentException>(() => CreateTaskAsync("", ""));
        }

        [Fact]
        public async Task ListTasksAsync_WithValidData_ShouldReturnTasks()
        {
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Criar uma tarefa para listar
            await CreateTaskAsync("Implement C# Agent", "This is a test task for implementing the C# Agent.");

            // Listar todas as tarefas
            var issues = await client.GetIssuesAsync();

            // Verificar se o número de tarefas é correto
        }

        private async Task CreateTaskAsync(string title, string description)
        {
            var task = new Issue()
            {
                Summary = title,
                Description = description,
                ProjectId = 12345, // ID do projeto em Jira
                PriorityId = 10001, // ID da prioridade na Jira
                StatusId = 10002, // ID do status na Jira (e.g., Open)
            };

            var issueCreated = await client.CreateIssueAsync(task);
            Console.WriteLine($"Task created: {issueCreated.Key}");
        }
    }
}