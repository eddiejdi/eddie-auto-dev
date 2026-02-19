using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharp Client
        var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Função para criar uma tarefa no Jira
        async Task CreateTask(string title, string description)
        {
            var task = new Task
            {
                Summary = title,
                Description = description,
                Priority = Priority.High,
                Assignee = new User { Name = "assignee-name" }
            };

            await jiraClient.CreateTask(task);
            Console.WriteLine("Tarefa criada com sucesso!");
        }

        // Função para monitorar a atividade de uma tarefa no Jira
        async Task MonitorTask(string taskId)
        {
            var task = await jiraClient.GetTask(taskId);
            Console.WriteLine($"Título: {task.Summary}");
            Console.WriteLine($"Descrição: {task.Description}");
            Console.WriteLine($"Prioridade: {task.Priority}");
            Console.WriteLine($"Atribuído a: {task.Assignee.Name}");
        }

        // Função para gerenciar tarefas no Jira
        async Task ManageTasks()
        {
            var tasks = await jiraClient.GetTasks();
            foreach (var task in tasks)
            {
                Console.WriteLine($"Título: {task.Summary}");
            }
        }

        // Exemplo de uso das funções
        await CreateTask("Teste Tarefa", "Descrição da tarefa para teste.");
        await MonitorTask("12345");
        await ManageTasks();
    }
}