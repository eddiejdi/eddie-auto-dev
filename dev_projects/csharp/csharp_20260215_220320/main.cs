using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharpClient
        var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Função para criar uma nova tarefa no Jira
        async Task CreateTaskAsync(string title, string description)
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

        // Função para listar todas as tarefas no Jira
        async Task ListTasksAsync()
        {
            var issues = await client.GetIssuesAsync();
            foreach (var issue in issues)
            {
                Console.WriteLine($"{issue.Key}: {issue.Summary}");
            }
        }

        // Exemplo de uso das funções
        await CreateTaskAsync("Implement C# Agent", "This is a test task for implementing the C# Agent.");
        await ListTasksAsync();
    }
}