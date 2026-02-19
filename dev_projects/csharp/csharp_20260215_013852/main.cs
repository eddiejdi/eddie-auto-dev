using System;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJira
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net");

            // Autenticação (substitua pelo seu token de autenticação)
            await jiraClient.AuthenticateAsync("your-token");

            // Criar uma nova tarefa
            var task = new Task
            {
                Summary = "Criar um novo item na lista",
                Description = "Este é o corpo da descrição da tarefa.",
                Assignee = "user-123"
            };

            // Adicionar a tarefa à lista (substitua pelo ID da sua lista)
            var listId = 12345;
            await jiraClient.Tasks.AddAsync(listId, task);

            Console.WriteLine("Tarefa criada com sucesso!");
        }
    }
}