using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharpClient;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Função para criar um novo ticket no Jira
            await CreateTicket(jiraClient, "New Feature Request", "Implement a new feature in the application.");

            Console.WriteLine("Ticket created successfully.");
        }

        static async Task CreateTicket(JiraClient jiraClient, string summary, string description)
        {
            try
            {
                // Cria um novo ticket
                var issue = new Issue
                {
                    Summary = summary,
                    Description = description,
                    ProjectKey = "YOUR_PROJECT_KEY", // Substitua pelo código do projeto no Jira
                    Priority = "High",
                    Status = "To Do"
                };

                // Envia o ticket para a API do Jira
                var createdIssue = await jiraClient.CreateIssue(issue);

                Console.WriteLine($"Ticket created with ID: {createdIssue.Id}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error creating ticket: {ex.Message}");
            }
        }
    }
}