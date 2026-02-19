using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharp.Client
        var client = new Client("https://your-jira-instance.atlassian.net", "username", "password");

        // Função para criar uma nova tarefa no Jira
        async Task CreateTaskAsync(string title, string description)
        {
            var task = await client.CreateIssueAsync(title: title, description: description);
            Console.WriteLine($"Tarefa criada com ID: {task.Id}");
        }

        // Função para atualizar uma tarefa existente no Jira
        async Task UpdateTaskAsync(string taskId, string newTitle, string newDescription)
        {
            var task = await client.GetIssueAsync(taskId);
            task.Title = newTitle;
            task.Description = newDescription;
            await client.UpdateIssueAsync(task);
            Console.WriteLine($"Tarefa atualizada com ID: {taskId}");
        }

        // Função para listar todas as tarefas do usuário no Jira
        async Task ListTasksAsync()
        {
            var issues = await client.GetIssuesAsync();
            foreach (var issue in issues)
            {
                Console.WriteLine($"ID: {issue.Id}, Título: {issue.Title}");
            }
        }

        // Exemplo de uso das funções
        await CreateTaskAsync("Teste C# Agent", "Integração com Jira");
        await UpdateTaskAsync("12345", "Teste atualizado C# Agent", "Integração com Jira atualizada");
        await ListTasksAsync();
    }
}