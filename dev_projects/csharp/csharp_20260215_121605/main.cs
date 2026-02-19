using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharp
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Função para criar uma tarefa no Jira
        async Task CreateTaskAsync(string summary, string description)
        {
            var task = await jira.CreateIssueAsync(
                "Bug",
                new Dictionary<string, object>
                {
                    { "summary", summary },
                    { "description", description }
                });

            Console.WriteLine($"Tarefa criada com ID: {task.Id}");
        }

        // Função para monitorar atividades do Jira
        async Task MonitorTasksAsync()
        {
            var issues = await jira.GetIssuesAsync("Bug");

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue ID: {issue.Id}, Summary: {issue.Summary}");
            }
        }

        // Função principal para executar as funcionalidades
        async Task MainAsync()
        {
            try
            {
                await CreateTaskAsync("Implement SCRUM-14", "Integrating C# Agent with Jira");
                await MonitorTasksAsync();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro: {ex.Message}");
            }
        }

        MainAsync().Wait();
    }
}