import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.security.SecurityLevel;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;
import com.atlassian.plugin.spring.scanner.annotation.ExtensionPoint;
import com.atlassian.plugin.spring.scanner.annotation.Plugin;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.List;

@Plugin("com.example.javaagent")
@ComponentScan(basePackages = "com.example.javaagent")
public class JavaAgent {

    @Autowired
    private Jira jira;

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private CustomFieldManager customFieldManager;

    @Autowired
    private ProjectManager projectManager;

    public void monitor() {
        List<Project> projects = projectManager.getAllProjects();
        for (Project project : projects) {
            List<Issue> issues = jira.getIssueManager().searchIssues("project = " + project.getKey(), null, false);
            for (Issue issue : issues) {
                // Implemente aqui a lógica para monitorar atividades do issue
                System.out.println("Monitoring issue: " + issue.getKey());
                // Adicione aqui o código para monitorar as atividades do issue
            }
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.monitor();
    }
}