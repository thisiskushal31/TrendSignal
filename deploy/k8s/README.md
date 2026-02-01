# Deploy on Kubernetes (cloud)

Deploy TrendSignal to any Kubernetes cluster (EKS, GKE, AKS, or self-hosted).

---

## Prerequisites

- `kubectl` configured for your cluster
- Image available to the cluster:
  - **Same machine:** from repo root: `docker build -f deploy/Dockerfile -t trend-signal:latest .` then (minikube) `minikube image load trend-signal:latest`
  - **Registry:** from repo root: build with `deploy/Dockerfile`, tag, push to your registry and set `image` in `deployment.yaml`

---

## 1. Create the Secret (OPENAI_API_KEY)

Do **not** commit the real key. Create the secret once:

```bash
kubectl create secret generic trend-signal-secret \
  --from-literal=OPENAI_API_KEY=sk-your-openai-key-here
```

Or from a file:

```bash
echo -n "sk-your-key" > /tmp/openai-key
kubectl create secret generic trend-signal-secret --from-file=OPENAI_API_KEY=/tmp/openai-key
rm /tmp/openai-key
```

---

## 2. Deploy

If using a **registry image**, edit `deployment.yaml` and set `image` to your image (e.g. `gcr.io/my-project/trend-signal:v1`).

```bash
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml
```

---

## 3. Access

- **ClusterIP (default):** Port-forward to test:
  ```bash
  kubectl port-forward svc/trend-signal 8001:80
  ```
  (Service exposes port 80, which forwards to container port 8001.)
  Then open http://localhost:8001

- **LoadBalancer:** Change `type` in `service.yaml` to `LoadBalancer`, apply, then use the external IP.

- **Ingress:** Apply `ingress.yaml` after editing the host and ingress class for your cluster. Ensure an Ingress controller (e.g. nginx) is installed.

---

## 4. Optional: Ingress

Edit `deploy/k8s/ingress.yaml` (host, ingressClassName, TLS), then:

```bash
kubectl apply -f deploy/k8s/ingress.yaml
```

Point your DNS to the Ingress LB and open https://trend-signal.example.com
