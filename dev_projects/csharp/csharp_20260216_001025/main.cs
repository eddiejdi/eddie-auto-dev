using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Função para criar uma tarefa no Jira
        async Task CreateTaskAsync()
        {
            var projectKey = "YOUR_PROJECT_KEY";
            var summary = "New C# Agent Integration";
            var description = "This is a new task to integrate the C# Agent with Jira.";

            var issue = await client.CreateIssueAsync(
                projectKey,
                summary,
                description
            );

            Console.WriteLine($"Task created: {issue.Key}");
        }

        // Função para listar todas as tarefas do projeto no Jira
        async Task ListTasksAsync()
        {
            var projectKey = "YOUR_PROJECT_KEY";

            var issues = await client.GetIssuesAsync(projectKey);

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue: {issue.Key} - Summary: {issue.Summary}");
            }
        }

        // Função para atualizar uma tarefa no Jira
        async Task UpdateTaskAsync()
        {
            var projectKey = "YOUR_PROJECT_KEY";
            var issueKey = "YOUR_TASK_KEY";

            var summary = "Updated C# Agent Integration";
            var description = "This is an updated task to integrate the C# Agent with Jira.";

            await client.UpdateIssueAsync(
                projectKey,
                issueKey,
                summary,
                description
            );

            Console.WriteLine($"Task updated: {issueKey}");
        }

        // Função para deletar uma tarefa no Jira
        async Task DeleteTaskAsync()
        {
            var projectKey = "YOUR_PROJECT_KEY";
            var issueKey = "YOUR_TASK_KEY";

            await client.DeleteIssueAsync(projectKey, issueKey);

            Console.WriteLine($"Task deleted: {issueKey}");
        }

        // Função principal para executar as funcionalidades
        async Task MainAsync()
        {
            await CreateTaskAsync();
            await ListTasksAsync();
            await UpdateTaskAsync();
            await DeleteTaskAsync();
        }
    }
}