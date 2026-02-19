using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

// Define a class to represent a task in Jira
public class Task
{
    public int Id { get; set; }
    public string Title { get; set; }
    public string Description { get; set; }
    public DateTime CreatedAt { get; set; }
}

// Define a class to represent the C# Agent
public class CSharpAgent
{
    private List<Task> tasks = new List<Task>();

    // Method to add a task to the list
    public void AddTask(Task task)
    {
        tasks.Add(task);
    }

    // Method to get all tasks from the list
    public IEnumerable<Task> GetAllTasks()
    {
        return tasks;
    }
}

// Define a class to represent the Jira client
public class JiraClient
{
    private CSharpAgent agent;

    public JiraClient(CSharpAgent agent)
    {
        this.agent = agent;
    }

    // Method to monitor events and log them
    public void MonitorEvents()
    {
        foreach (var task in agent.GetAllTasks())
        {
            Console.WriteLine($"Task {task.Title} created at {task.CreatedAt}");
        }
    }
}

// Main method to run the C# Agent with Jira integration
public class Program
{
    public static async Task Main(string[] args)
    {
        // Create a new instance of the CSharpAgent
        var agent = new CSharpAgent();

        // Add some tasks to the agent
        agent.AddTask(new Task { Id = 1, Title = "Task 1", Description = "Description for task 1", CreatedAt = DateTime.Now });
        agent.AddTask(new Task { Id = 2, Title = "Task 2", Description = "Description for task 2", CreatedAt = DateTime.Now });

        // Create a new instance of the JiraClient
        var jiraClient = new JiraClient(agent);

        // Monitor events and log them to the console
        await jiraClient.MonitorEvents();
    }
}