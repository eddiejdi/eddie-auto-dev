import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.service.ServiceContextFactory;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

public class JavaAgentTest {

    private Jira jira = new Jira();
    private JiraServiceContext serviceContext = ServiceContextFactory.getJiraServiceContext(jira);

    @org.junit.Test
    public void testCreateIssueSuccess() {
        Project project = new Project("MyProject", "MyProject");
        String summary = "New Task";
        String description = "Implement a new feature in the application.";

        createIssue(serviceContext, project, summary, description);
    }

    @org.junit.Test(expected = IllegalArgumentException.class)
    public void testCreateIssueInvalidSummary() {
        Project project = new Project("MyProject", "MyProject");
        String summary = null;
        String description = "Implement a new feature in the application.";

        createIssue(serviceContext, project, summary, description);
    }

    @org.junit.Test(expected = IllegalArgumentException.class)
    public void testCreateIssueInvalidDescription() {
        Project project = new Project("MyProject", "MyProject");
        String summary = "New Task";
        String description = null;

        createIssue(serviceContext, project, summary, description);
    }

    private static void createIssue(JiraServiceContext serviceContext, Project project, String summary, String description) {
        try {
            // Implementação para criar uma issue no Jira
            // Aqui você pode usar o Jira API para criar a issue
            // Exemplo:
            // jira.createIssue(serviceContext, project.getKey(), summary, description);
            System.out.println("Issue created successfully.");
        } catch (Exception e) {
            fail("Error creating issue: " + e.getMessage());
        }
    }
}