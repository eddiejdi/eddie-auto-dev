using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do JiraSharp
            var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria um novo issue
            var issue = new Issue
            {
                Summary = "Teste de C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Priority = "High"
            };

            try
            {
                // Criando o issue no Jira
                var createdIssue = await jiraClient.CreateIssueAsync(issue);

                Console.WriteLine($"Issue criado: {createdIssue.Key}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro ao criar issue: {ex.Message}");
            }

            // Fechando a conexão com o Jira
            await jiraClient.CloseConnectionAsync();
        }
    }
}