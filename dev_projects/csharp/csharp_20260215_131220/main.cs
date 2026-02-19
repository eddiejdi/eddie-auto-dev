using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do cliente Jira
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                // Cria um novo ticket no Jira
                var issue = await client.CreateIssueAsync(
                    projectKey: "YOUR_PROJECT_KEY",
                    summary: "Teste do CSharp Agent com Jira",
                    description: "Este é um teste para integrar o CSharp Agent com Jira",
                    priorityId: 1,
                    assigneeId: 10345
                );

                Console.WriteLine($"Ticket criado: {issue.Key}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro ao criar ticket no Jira: {ex.Message}");
            }
        }
    }
}