using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_WithValidData_ShouldReturnCreatedIssue()
        {
            // Configuração do JiraSharp Client
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Cria um novo ticket
            var issue = new Issue()
            {
                Title = "Teste de C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            try
            {
                // Cria o ticket no Jira
                var createdIssue = await client.CreateIssueAsync(issue);

                Assert.NotNull(createdIssue);
                Assert.NotEmpty(createdIssue.Key);
            }
            catch (Exception ex)
            {
                Assert.Fail($"Erro ao criar ticket: {ex.Message}");
            }
        }

        [Fact]
        public async Task CreateIssueAsync_WithInvalidData_ShouldThrowException()
        {
            // Configuração do JiraSharp Client
            var client = new JiraSharpClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Cria um novo ticket com valores inválidos
            var issue = new Issue()
            {
                Title = null,
                Description = "",
                ProjectKey = null
            };

            try
            {
                await client.CreateIssueAsync(issue);
                Assert.Fail("Deveria lançar uma exceção");
            }
            catch (Exception ex)
            {
                // Verifique se a exceção é do tipo esperado
                var jiraSharpException = ex as JiraSharpException;
                Assert.NotNull(jiraSharpException);
                Assert.Equal("Invalid issue data", jiraSharpException.Message);
            }
        }

        [Fact]
        public async Task CreateIssueAsync_WithNullClient_ShouldThrowException()
        {
            // Configuração do JiraSharp Client
            var client = null;

            // Cria um novo ticket com valores inválidos
            var issue = new Issue()
            {
                Title = "Teste de C# Agent com Jira",
                Description = "",
                ProjectKey = null
            };

            try
            {
                await client.CreateIssueAsync(issue);
                Assert.Fail("Deveria lançar uma exceção");
            }
            catch (Exception ex)
            {
                // Verifique se a exceção é do tipo esperado
                var jiraSharpException = ex as JiraSharpException;
                Assert.NotNull(jiraSharpException);
                Assert.Equal("Invalid client", jiraSharpException.Message);
            }
        }
    }
}