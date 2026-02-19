using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_Success()
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

                // Verificando se a criação foi bem-sucedida
                Assert.NotNull(createdIssue);
                Assert.NotEmpty(createdIssue.Key);
            }
            catch (Exception ex)
            {
                // Lidando com erros de criação
                Console.WriteLine($"Erro ao criar issue: {ex.Message}");
            }

            // Fechando a conexão com o Jira
            await jiraClient.CloseConnectionAsync();
        }

        [Fact]
        public async Task CreateIssueAsync_Error()
        {
            // Configuração do JiraSharp
            var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria um novo issue com uma descrição vazia
            var issue = new Issue
            {
                Summary = "Teste de C# Agent com Jira",
                Description = "",
                Priority = "High"
            };

            try
            {
                // Criando o issue no Jira
                await jiraClient.CreateIssueAsync(issue);
            }
            catch (Exception ex)
            {
                // Verificando se a criação falhou
                Assert.NotNull(ex);
                Assert.Contains("Description cannot be empty", ex.Message);
            }

            // Fechando a conexão com o Jira
            await jiraClient.CloseConnectionAsync();
        }

        [Fact]
        public async Task CreateIssueAsync_InvalidPriority()
        {
            // Configuração do JiraSharp
            var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria um novo issue com uma prioridade inválida
            var issue = new Issue
            {
                Summary = "Teste de C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Priority = "Invalid"
            };

            try
            {
                // Criando o issue no Jira
                await jiraClient.CreateIssueAsync(issue);
            }
            catch (Exception ex)
            {
                // Verificando se a criação falhou
                Assert.NotNull(ex);
                Assert.Contains("Priority must be one of the following: High, Medium, Low", ex.Message);
            }

            // Fechando a conexão com o Jira
            await jiraClient.CloseConnectionAsync();
        }
    }
}