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
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Função para registrar uma tarefa no Jira
        async Task RegisterTaskAsync(string title, string description)
        {
            var task = new Issue
            {
                Summary = title,
                Description = description
            };

            await jiraClient.CreateIssue(task);
            Console.WriteLine($"Tarefa '{title}' criada com sucesso.");
        }

        // Função para monitorar o progresso da tarefa no Jira
        async Task MonitorTaskProgressAsync(string issueKey)
        {
            var issue = await jiraClient.GetIssue(issueKey);

            if (issue != null)
            {
                Console.WriteLine($"Tarefa '{issue.Key}':");
                Console.WriteLine($"Status: {issue.Fields.Status.Name}");
                Console.WriteLine($"Descrição: {issue.Fields.Description}");
            }
            else
            {
                Console.WriteLine("Tarefa não encontrada.");
            }
        }

        // Exemplo de uso das funções
        await RegisterTaskAsync("Implementar SCRUM-14", "Integração com Jira para tracking de atividades em C#.");

        await MonitorTaskProgressAsync("SCRUM-14");
    }
}