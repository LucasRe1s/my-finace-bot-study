-- Módulo de pedidos: schema inicial.
-- Acesso a dados somente pelo servidor (service role). RLS habilitado sem
-- policies bloqueia anon/authenticated mesmo com a anon key pública.

CREATE TABLE public.products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(trim(name)) > 0),
  description text NOT NULL DEFAULT '',
  units_per_box integer NOT NULL CHECK (units_per_box > 0),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  number bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
  customer_name text NOT NULL CHECK (length(trim(customer_name)) > 0),
  notes text NOT NULL DEFAULT '',
  status text NOT NULL CHECK (status IN (
    'erro_envio', 'enviado', 'aceito', 'recusado', 'em_entrega', 'entregue', 'cancelado'
  )),
  telegram_message_id bigint,
  created_by uuid NOT NULL REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX orders_status_created_at_idx ON public.orders (status, created_at DESC);

CREATE TABLE public.order_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  product_id uuid NOT NULL REFERENCES public.products(id),
  product_name text NOT NULL,
  units_per_box integer NOT NULL,
  boxes integer NOT NULL CHECK (boxes > 0)
);

CREATE INDEX order_items_order_id_idx ON public.order_items (order_id);

CREATE TABLE public.order_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  from_status text,
  to_status text NOT NULL,
  actor text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX order_events_order_id_idx ON public.order_events (order_id, created_at);

-- Linha única de configuração.
CREATE TABLE public.settings (
  id boolean PRIMARY KEY DEFAULT true CHECK (id),
  granja_chat_id bigint,
  link_code text,
  link_code_expires_at timestamptz
);

INSERT INTO public.settings (id) VALUES (true);

ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.products, public.orders, public.order_items, public.order_events, public.settings
  FROM anon, authenticated;

-- Cria pedido + itens numa transação, copiando nome e unidades/caixa do produto.
-- p_items: [{"product_id": "<uuid>", "boxes": 10}, ...]
CREATE FUNCTION public.create_order(
  p_customer_name text,
  p_notes text,
  p_created_by uuid,
  p_items jsonb
) RETURNS uuid
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  v_order_id uuid;
  v_item jsonb;
  v_product public.products%ROWTYPE;
  v_boxes integer;
BEGIN
  IF jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
    RAISE EXCEPTION 'Pedido sem itens';
  END IF;

  INSERT INTO public.orders (customer_name, notes, status, created_by)
  VALUES (trim(p_customer_name), coalesce(p_notes, ''), 'enviado', p_created_by)
  RETURNING id INTO v_order_id;

  FOR v_item IN SELECT * FROM jsonb_array_elements(p_items) LOOP
    v_boxes := (v_item->>'boxes')::integer;
    IF v_boxes IS NULL OR v_boxes <= 0 THEN
      RAISE EXCEPTION 'Quantidade de caixas inválida';
    END IF;

    SELECT * INTO v_product FROM public.products
    WHERE id = (v_item->>'product_id')::uuid AND active;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Produto inexistente ou inativo: %', v_item->>'product_id';
    END IF;

    INSERT INTO public.order_items (order_id, product_id, product_name, units_per_box, boxes)
    VALUES (v_order_id, v_product.id, v_product.name, v_product.units_per_box, v_boxes);
  END LOOP;

  INSERT INTO public.order_events (order_id, from_status, to_status, actor)
  VALUES (v_order_id, NULL, 'enviado', 'web');

  RETURN v_order_id;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.create_order(text, text, uuid, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_order(text, text, uuid, jsonb) TO service_role;

-- Transição condicional: só altera se o status atual for o esperado.
-- Retorna true se aplicou (e registra o evento), false se o status já mudou.
CREATE FUNCTION public.transition_order(
  p_order_id uuid,
  p_from text,
  p_to text,
  p_actor text
) RETURNS boolean
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  UPDATE public.orders SET status = p_to, updated_at = now()
  WHERE id = p_order_id AND status = p_from;
  IF NOT FOUND THEN
    RETURN false;
  END IF;

  INSERT INTO public.order_events (order_id, from_status, to_status, actor)
  VALUES (p_order_id, p_from, p_to, p_actor);
  RETURN true;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.transition_order(uuid, text, text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.transition_order(uuid, text, text, text) TO service_role;
