using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace YourNamespace.Tests
{
    public class ProgramTests
    {
        private readonly JiraClient _client;

        public ProgramTests()
        {
            _client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        }

        [Fact]
        public async Task CreateTaskAsync_WithValidInputs_ShouldCreateTask()
        {
            var title = "Implement SCRUM-14";
            var description = "Integrar C# Agent com Jira";

            await _client.Tasks.CreateAsync(title, description);

            // Verifique se a tarefa foi criada (pode ser necessário usar um método para verificar isso)
        }

        [Fact]
        public async Task CreateTaskAsync_WithInvalidInputs_ShouldThrowException()
        {
            var title = "";
            var description = "Integrar C# Agent com Jira";

            await Assert.ThrowsAsync<ArgumentException>(() => _client.Tasks.CreateAsync(title, description));
        }

        // Adicione testes para outras funções e métodos públicos do Program.cs
    }
}