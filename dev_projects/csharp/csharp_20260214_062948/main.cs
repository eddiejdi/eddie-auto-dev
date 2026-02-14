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

            // Função para monitorar atividades
            await MonitorActivities(client);

            Console.WriteLine("Programa finalizado.");
        }

        static async Task MonitorActivities(JiraClient client)
        {
            var issues = await client.GetIssuesAsync();

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue: {issue.Key}, Status: {issue.Fields.Status.Name}");
            }
        }
    }
}