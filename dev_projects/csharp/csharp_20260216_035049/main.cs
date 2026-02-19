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
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Função para criar uma tarefa no Jira
        async Task CreateTaskAsync(string projectKey, string summary)
        {
            var task = new Issue
            {
                Key = client.GenerateIssueKey(projectKey),
                Fields = new IssueFields
                {
                    Project = new Project { Key = projectKey },
                    Summary = summary,
                    Description = "This is a test task created by the C# Agent."
                }
            };

            await client.CreateIssueAsync(task);
        }

        // Função para listar todas as tarefas do projeto
        async Task ListTasksAsync(string projectKey)
        {
            var issues = await client.SearchIssuesAsync(new SearchOptions { Jql = $"project = {projectKey}" });

            foreach (var issue in issues.Items)
            {
                Console.WriteLine($"Issue: {issue.Key} - Summary: {issue.Fields.Summary}");
            }
        }

        // Função para atualizar uma tarefa no Jira
        async Task UpdateTaskAsync(string projectKey, string issueKey, string summary)
        {
            var issue = await client.GetIssueAsync(issueKey);

            if (issue != null)
            {
                issue.Fields.Summary = summary;
                await client.UpdateIssueAsync(issue);
            }
        }

        // Função para deletar uma tarefa no Jira
        async Task DeleteTaskAsync(string projectKey, string issueKey)
        {
            var issue = await client.GetIssueAsync(issueKey);

            if (issue != null)
            {
                await client.DeleteIssueAsync(issue.Key);
            }
        }

        // Exemplo de uso das funções
        try
        {
            await CreateTaskAsync("YOUR-PROJECT-KEY", "Test Task");
            await ListTasksAsync("YOUR-PROJECT-KEY");
            await UpdateTaskAsync("YOUR-PROJECT-KEY", "TEST TASK", "Updated Test Task");
            await DeleteTaskAsync("YOUR-PROJECT-KEY", "TEST TASK");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }
}