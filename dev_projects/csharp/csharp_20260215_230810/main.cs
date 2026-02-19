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

        // Função para criar um novo ticket no Jira
        async Task CreateTicketAsync()
        {
            try
            {
                var issue = new Issue
                {
                    Summary = "Teste de C# Agent com Jira",
                    Description = "Este é um teste para integrar o C# Agent com Jira.",
                    Project = new Project { Key = "YOUR-PROJECT" },
                    Priority = new Priority { Name = "High" }
                };

                var createdIssue = await client.Issue.CreateAsync(issue);
                Console.WriteLine($"Ticket criado: {createdIssue.Key}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro ao criar ticket: {ex.Message}");
            }
        }

        // Função para atualizar um ticket no Jira
        async Task UpdateTicketAsync()
        {
            try
            {
                var issueKey = "YOUR-ISSUE-Key";
                var update = new IssueUpdate
                {
                    Summary = "Teste de C# Agent com Jira - Atualização",
                    Description = "Este é um teste para atualizar o ticket no Jira."
                };

                var updatedIssue = await client.Issue.UpdateAsync(issueKey, update);
                Console.WriteLine($"Ticket atualizado: {updatedIssue.Key}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro ao atualizar ticket: {ex.Message}");
            }
        }

        // Função para deletar um ticket no Jira
        async Task DeleteTicketAsync()
        {
            try
            {
                var issueKey = "YOUR-ISSUE-Key";
                await client.Issue.DeleteAsync(issueKey);
                Console.WriteLine($"Ticket deletado: {issueKey}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro ao deletar ticket: {ex.Message}");
            }
        }

        // Executa as funções de teste
        await CreateTicketAsync();
        await UpdateTicketAsync();
        await DeleteTicketAsync();
    }
}